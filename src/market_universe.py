"""Versioned, explicitly reviewed market universe independent of owned quantities."""

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import time

import pandas as pd

from collection_runtime import RetryingSteam, collection_lock
from global_analysis import market_indices
from portfolio_data import HOLDINGS, PRICES, ROOT, _parse_dates, atomic_csv, identity, validate_prices
from update_market_prices import validate_catalog


def timestamp(value):
    return _parse_dates(pd.Series([value]), "universe timestamp").iloc[0]


def validate_release(release):
    """Accept exact listings only; names/variants are never synthesized."""
    if not isinstance(release, dict) or release.get("schema") != 1:
        raise ValueError("Expected universe schema 1")
    for key in ("source_url", "source_revision", "scope"):
        if not isinstance(release.get(key), str) or not release[key].strip():
            raise ValueError(f"Missing {key}")
    if timestamp(release["source_updated_at"]) > timestamp(release["collected_at"]):
        raise ValueError("Source update follows collection")
    items = release.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("Expected a nonempty reviewed listing selection")
    frame = pd.DataFrame(items)
    required = {"item_id", "category", "item_name", "market_hash_name", "source_id", "wear", "variant", "collection"}
    if not required.issubset(frame):
        raise ValueError("Missing listing metadata")
    validate_catalog(frame, frame.assign(quantity=0)[HOLDINGS])
    if frame.source_id.map(lambda v: not isinstance(v, str) or not v.strip()).any() or frame.source_id.duplicated().any():
        raise ValueError("Expected unique source variant IDs")
    if not frame.variant.isin(["normal", "stattrak", "souvenir"]).all():
        raise ValueError("Unknown listing variant")
    for column in ("wear", "collection"):
        if not frame[column].map(lambda v: v is None or isinstance(v, str)).all():
            raise ValueError(f"Invalid {column}")
    return frame


def release_id(release):
    validate_release(release)
    return sha256(json.dumps(release, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def publish(release, root=ROOT, environment="school"):
    """Immutable releases keep historical membership and exact prior names."""
    if environment != "home":
        raise ValueError("Publishing requires home; school is read-only")
    key = release_id(release)
    directory = Path(root) / "data/market/releases"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{key}.json"
    # Exclusive creation also makes repeated publication harmless.
    try:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(release, stream, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except FileExistsError:
        if json.loads(path.read_text(encoding="utf-8")) != release:
            raise ValueError("Release integrity mismatch")
    return key


def load_release(root, key, as_of):
    if not isinstance(key, str) or len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
        raise ValueError("Invalid release ID")
    release = json.loads((Path(root) / "data/market/releases" / f"{key}.json").read_text(encoding="utf-8"))
    if release_id(release) != key or timestamp(release["collected_at"]) > timestamp(as_of):
        raise ValueError("Release unavailable at analysis origin or corrupt")
    return release, validate_release(release)


def collect(root, key, watchlist, *, environment="school", now=None, budget=20, fetch=None, pause=time.sleep):
    """Explicit finite selection; at most budget requests, with bounded transport retries."""
    if environment not in ("school", "home") or type(budget) is not int or not 0 <= budget <= 1000:
        raise ValueError("Invalid environment or request budget (0..1000)")
    now = timestamp(now if now is not None else pd.Timestamp.now())
    _, universe = load_release(root, key, now)
    if len(set(watchlist)) != len(watchlist) or not set(watchlist).issubset(universe.item_id):
        raise ValueError("Watchlist must contain unique known identities")
    selected = universe.set_index("item_id").loc[watchlist].reset_index()
    target = Path(root) / "data/market/observations.csv"
    history = validate_prices(pd.read_csv(target)) if target.exists() else pd.DataFrame(columns=PRICES)
    outcomes = {item: "not_requested" for item in watchlist}
    if environment == "home":
        fetch = fetch or RetryingSteam(attempts=1)
        with collection_lock(root):
            # Read again under lock to preserve observations from another collector.
            history = validate_prices(pd.read_csv(target)) if target.exists() else pd.DataFrame(columns=PRICES)
            rows = []
            for index, row in enumerate(selected.iloc[:budget].itertuples(index=False)):
                if index:
                    pause(2)
                try:
                    price = fetch(row.market_hash_name)
                except (TimeoutError, ConnectionError, OSError):
                    price = None
                valid = isinstance(price, (int, float)) and not isinstance(price, bool) and math.isfinite(price) and price >= 0
                outcomes[row.item_id] = "updated" if valid else "unavailable"
                if valid:
                    rows.append(dict(date=now, item_id=row.item_id, category=row.category, item_name=row.item_name,
                                     unit_price=price, source="steam", currency="EUR", date_estimated=False))
            if rows:
                history = validate_prices(pd.concat([history, pd.DataFrame(rows)], ignore_index=True))
                history = history.drop_duplicates(["date", "item_id", "source"], keep="last")
                atomic_csv(history, target)
    eligible = history.loc[history.date.le(now) & history.unit_price.notna()]
    latest = eligible.sort_values("date", kind="stable").drop_duplicates("item_id", keep="last")
    report = selected.merge(latest[["item_id", "date", "unit_price"]], on="item_id", how="left")
    report["outcome"] = report.item_id.map(outcomes)
    report["date"] = pd.to_datetime(report.date)
    report["age_days"] = (now - report.date).dt.total_seconds() / 86400
    return report


def indices(root, key, watchlist, as_of, max_age_days=45):
    release, frame = load_release(root, key, as_of)
    if not set(watchlist).issubset(frame.item_id) or len(set(watchlist)) != len(watchlist):
        raise ValueError("Invalid index cohort")
    frame = frame.loc[frame.item_id.isin(watchlist)].assign(quantity=0)
    path = Path(root) / "data/market/observations.csv"
    prices = validate_prices(pd.read_csv(path)) if path.exists() else pd.DataFrame(columns=PRICES)
    # A newly imported universe cannot be treated as known in earlier history.
    prices = prices.loc[prices.date.ge(timestamp(release["collected_at"])) & prices.date.le(timestamp(as_of))]
    result, diagnostic = market_indices(frame[HOLDINGS], prices, max_age_days)
    diagnostic.update(release_id=key, cohort_ids=sorted(watchlist), scope=release["scope"])
    return result, diagnostic


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["home", "school"])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--publish", type=Path, help="Reviewed release JSON")
    parser.add_argument("--release")
    parser.add_argument("--watchlist", type=Path, help="JSON array of stable IDs")
    parser.add_argument("--budget", type=int, default=20)
    args = parser.parse_args()
    if args.publish:
        print(publish(json.loads(args.publish.read_text(encoding="utf-8")), args.root, args.environment))
    else:
        if not args.release or not args.watchlist:
            parser.error("--release and --watchlist required")
        print(collect(args.root, args.release, json.loads(args.watchlist.read_text(encoding="utf-8")),
                      environment=args.environment, budget=args.budget).to_string(index=False, na_rep="N/A"))
