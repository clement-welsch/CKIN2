"""Validate, collect, snapshot and report the portfolio in one command."""

import argparse
from datetime import datetime
from pathlib import Path
import time

import pandas as pd

from global_snapshots import COLUMNS, build_snapshot, save_snapshot, validate_snapshots, value_snapshots
from portfolio_data import FILES, ROOT, _parse_dates, load_holdings, load_prices
from update_market_prices import collect, validate_catalog

SUCCESS, PARTIAL, FAILURE = 0, 1, 2


def run(root=ROOT, environment="school", *, date=None, snapshot_path=None,
        clock=datetime.now, fetch=None, pause=time.sleep):
    """Return status and completed stages; preserve earlier successful writes."""
    stages, current, historical, collection = [], pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    stage = "validation"
    try:
        root = Path(root).resolve()
        if environment not in ("home", "school"):
            raise ValueError("Expected home or school")
        started = _parse_dates(pd.Series([clock()]), "run clock").iloc[0]
        requested = _parse_dates(pd.Series([date]), "execution date").iloc[0] if date is not None else started
        if environment == "home" and requested.date() != started.date():
            raise ValueError("Home cannot backdate live prices; --date must be today's local date")
        target = Path(snapshot_path).resolve() if snapshot_path else root / "data/processed/global_inventory_history.csv"
        protected = {root / "data/processed" / f"{prefix}_{suffix}.csv"
                     for prefix in FILES for suffix in ("inventory", "prices")}
        protected.update(root / "data/processed" / name for name in (
            "market_catalog.csv", "market_observations.csv", "transactions.csv", "opening_inventory.csv",
            "drop_cases_inventory_history.csv"))
        if target in protected:
            raise ValueError("Snapshot path must not overwrite an input or legacy history")
        holdings, imported = load_holdings(root)
        if not imported:
            raise ValueError("No inventory files imported; check --root")
        load_prices(root, holdings)  # Validate all source histories BEFORE network or writes.
        if environment == "home":
            validate_catalog(pd.read_csv(root / "data/processed/market_catalog.csv"), holdings)
        history = validate_snapshots(pd.read_csv(target)) if target.exists() else pd.DataFrame(columns=COLUMNS)
        stages.append(dict(stage=stage, status="ok", timestamp=started))

        stage = "collection"
        collection = collect(root, environment, now=started if environment == "home" else requested,
                             fetch=fetch, pause=pause, clock=clock if environment == "home" else None)
        failed = int(collection.outcome.eq("failed").sum())
        stages.append(dict(stage=stage, status="partial" if failed else "ok" if environment == "home" else "read_only",
                           failed_items=failed))

        stage = "snapshot"
        observed_at = _parse_dates(pd.Series([clock()]), "snapshot clock").iloc[0] if environment == "home" else requested
        if environment == "home" and observed_at < started:
            raise ValueError("Snapshot clock precedes collection start")
        if environment == "home":
            history = save_snapshot(holdings, imported, observed_at, target)
        stages.append(dict(stage=stage, status="saved" if environment == "home" else "read_only", timestamp=observed_at))

        stage = "report"
        prices = load_prices(root, holdings)
        detail, current = value_snapshots(build_snapshot(holdings, imported, observed_at), prices)
        _, historical = value_snapshots(history.loc[history.snapshot_date.le(observed_at)] if not history.empty else history, prices)
        incomplete = current.total_value.isna().any()
        stale = bool((detail.loc[detail.state.eq("holdings") & detail.quantity.ne(0), "price_age_days"] > 1).any())
        status = PARTIAL if failed or incomplete or stale else SUCCESS
        stages.append(dict(stage=stage, status="partial" if status == PARTIAL else "ok", timestamp=observed_at))
        print("\nCurrent portfolio (gross EUR; N/A means incomplete)")
        print(current.to_string(index=False, na_rep="N/A"))
        print("\nPrice dates and age in days")
        print(detail[["category", "item_name", "price_date", "price_age_days"]]
              .to_string(index=False, na_rep="N/A"))
        print("\nHistorical snapshots")
        print(historical.to_string(index=False, na_rep="N/A"))
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as error:
        status = FAILURE
        stages.append(dict(stage=stage, status="failed", error=str(error)))
    print("\nExecution summary")
    print(pd.DataFrame(stages).to_string(index=False, na_rep="N/A"))
    print(f"Exit status: {status} (0=success, 1=partial, 2=failure)")
    return dict(code=status, stages=stages, current=current, historical=historical, collection=collection)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["home", "school"])
    parser.add_argument("--root", type=Path, default=ROOT, help="Data root containing data/processed")
    parser.add_argument("--date", help="School valuation cutoff; home accepts only today's date and retains real timestamps")
    parser.add_argument("--snapshot-path", type=Path, help="Optional global history CSV; relative to current directory")
    args = parser.parse_args(argv)
    return run(args.root, args.environment, date=args.date, snapshot_path=args.snapshot_path)["code"]


if __name__ == "__main__":
    raise SystemExit(main())
