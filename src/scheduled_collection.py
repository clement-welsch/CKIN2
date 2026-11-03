"""Opt-in scheduled portfolio collection; all runtime state stays under data/."""

import argparse
from collections import Counter
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
import math
import os
from pathlib import Path
import tempfile
from uuid import uuid4
from zoneinfo import ZoneInfo

from collection_runtime import CollectionBusy, RetryingSteam, collection_lock
from portfolio_data import ROOT
from update_portfolio import FAILURE, _run, run

DEFAULTS = dict(interval_minutes=1440, timezone="Europe/Paris", attempts=3,
                base_delay_seconds=2, max_wait_seconds=120, stale_days=2,
                persistent_failures=3, notification="console")


def config_from(path=None):
    config = DEFAULTS.copy()
    if path:
        supplied = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(supplied, dict) or set(supplied) - set(DEFAULTS):
            raise ValueError("Unknown collection configuration fields")
        config.update(supplied)
    for key in ("interval_minutes", "attempts", "persistent_failures"):
        if type(config[key]) is not int or config[key] < 1:
            raise ValueError(f"{key} must be a positive integer")
    if config["attempts"] > 10 or config["interval_minutes"] > 525600:
        raise ValueError("Attempts or cadence exceed supported bounds")
    for key in ("base_delay_seconds", "max_wait_seconds", "stale_days"):
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"{key} must be finite and nonnegative")
    if config["max_wait_seconds"] > 3600:
        raise ValueError("Wait budget must not exceed one hour")
    if config["notification"] not in ("console", "none"):
        raise ValueError("Notifications support console or none only")
    ZoneInfo(config["timezone"])
    return config


def write_json(path, value):
    """Atomic state update; never persist raw output or inventory identifiers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def scheduled(root=ROOT, environment="school", *, config=None, due=False,
              clock=lambda: datetime.now(timezone.utc), fetch=None, pause=None):
    """Cadence is elapsed UTC time; configured timezone labels the event journal."""
    if environment == "school":
        # No scheduler lock, runtime directory, state, journal or notification writes.
        return run(root, "school")["code"]
    if environment != "home":
        raise ValueError("Expected home or school")
    config = config_from(config)
    root = Path(root)
    target = root / "data/runtime/collection-state.json"
    now = clock()
    if now.tzinfo is None:
        raise ValueError("Scheduler clock must be timezone-aware")
    try:
        with collection_lock(root):
            state = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
            interrupted = (root / "data/runtime/collection-active.json").exists()
            if due and not interrupted and state.get("next_due") and now < datetime.fromisoformat(state["next_due"]):
                print("Collection not due; no update performed")
                return 0
            transport = RetryingSteam(config["attempts"], config["base_delay_seconds"],
                                      config["max_wait_seconds"], clock=clock,
                                      **({"pause": pause} if pause is not None else {}))
            # Store the started event before the work: a crash remains detectable.
            started = now.isoformat()
            write_json(root / "data/runtime/collection-active.json", {"started": started})
            with redirect_stdout(StringIO()):
                result = _run(root, "home", fetch=fetch or transport,
                              **({"pause": pause} if pause is not None else {}))
            ended = clock()
            collection = result["collection"]
            updated = int(collection.outcome.eq("updated").sum()) if "outcome" in collection else 0
            failed = int(collection.outcome.eq("failed").sum()) if "outcome" in collection else 0
            stale = int((collection.age_days > config["stale_days"]).sum()) if "age_days" in collection else 0
            missing = int(collection.unit_price.isna().sum()) if "unit_price" in collection else 0
            streak = state.get("failure_streak", 0) + 1 if result["code"] else 0
            # Notify on condition changes, not on identical repeated failures.
            condition = dict(code=result["code"], stale=bool(stale), missing=bool(missing),
                             persistent=streak >= config["persistent_failures"],
                             failed_stages=[s["stage"] for s in result["stages"] if s["status"] == "failed"])
            changed = condition != state.get("condition")
            if changed and config["notification"] == "console":
                print(f"Collection changed: status={result['code']}, stale={stale}, missing={missing}, persistent={condition['persistent']}")
            next_due = ended + timedelta(minutes=config["interval_minutes"])
            deferrals = [datetime.fromisoformat(o["retry_at"]) for o in transport.outcomes if o.get("retry_at")]
            if deferrals:
                next_due = max([next_due, *deferrals])
            event = dict(started=started, ended=ended.isoformat(),
                         local_end=ended.astimezone(ZoneInfo(config["timezone"])).isoformat(),
                         code=result["code"], updated=updated, failed=failed, stale=stale,
                         missing=missing, outcomes=dict(Counter(o["kind"] for o in transport.outcomes)),
                         interrupted_previous=interrupted,
                         failed_stages=[s["stage"] for s in result["stages"] if s["status"] == "failed"],
                         next_due=next_due.isoformat(), condition_changed=changed)
            # One atomic file per run, bounded size and no raw exception/network output.
            event_name = ended.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex
            write_json(root / "data/runtime/runs" / (event_name + ".json"), event)
            write_json(target, dict(next_due=event["next_due"], failure_streak=streak, condition=condition,
                                    last_success=ended.isoformat() if result["code"] == 0 else state.get("last_success"),
                                    last_end=ended.isoformat()))
            (root / "data/runtime/collection-active.json").unlink()
            print(f"Collection exit={result['code']}; updated={updated}; failed={failed}; next={event['next_due']}")
            return result["code"]
    except CollectionBusy:
        print("Collection already active; skipped")
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["home", "school"])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--due", action="store_true", help="Only collect after the saved next_due instant")
    args = parser.parse_args(argv)
    try:
        return scheduled(args.root, args.environment, config=args.config, due=args.due)
    except (OSError, ValueError, TypeError, KeyError):
        print("Scheduler configuration or runtime state invalid/unavailable; no raw details logged")
        return FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
