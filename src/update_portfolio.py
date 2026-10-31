"""Validate, collect, snapshot and report the complete local portfolio."""

import argparse
from pathlib import Path

import pandas as pd

from global_analysis import analyze
from global_snapshots import save_snapshot, validate_snapshots
from portfolio_data import ROOT, load_holdings, load_prices
from update_market_prices import collect, validate_catalog

SUCCESS, PARTIAL, FAILURE = 0, 1, 2


def run(root=ROOT, environment="school", *, when=None, fetch=None, pause=None):
    """Return 0 for complete success, 1 for partial coverage, 2 for failure.

    Each persisted file is atomic independently. A successful price collection
    is retained if snapshot persistence or reporting subsequently fails.
    """
    root = Path(root)
    stage = "validation"
    try:
        if environment not in ("home", "school"):
            raise ValueError("Unknown environment")
        stamp = pd.Timestamp.now().floor("s") if when is None else pd.Timestamp(when)
        if pd.isna(stamp) or stamp.tzinfo is not None:
            raise ValueError("Expected a local timezone-naive execution timestamp")
        holdings, imported = load_holdings(root)
        load_prices(root, holdings)
        history_path = root / "data/processed/global_inventory_history.csv"
        if history_path.exists():
            validate_snapshots(pd.read_csv(history_path))
        catalog_path = root / "data/processed/market_catalog.csv"
        if environment == "home" or catalog_path.exists():
            validate_catalog(pd.read_csv(catalog_path), holdings)
        print(f"validation: OK; {len(holdings)} items; {len(imported)}/6 categories imported")

        stage = "collection"
        options = {"fetch": fetch}
        if pause is not None:
            options["pause"] = pause
        # An explicitly supplied timestamp is also the deterministic retry key.
        collected = collect(root, environment, now=stamp if when is not None else None, **options)
        failures = int(collected.outcome.eq("failed").sum())
        print(f"collection: {failures} failed; {environment}")

        stage = "snapshot"
        # With a real clock, record when collection finished, not when it began.
        snapshot_time = stamp if when is not None else pd.Timestamp.now().floor("s")
        if environment == "home":
            save_snapshot(holdings, imported, snapshot_time, history_path)
            print(f"snapshot: saved at {snapshot_time}")
        else:
            print("snapshot: read-only; no snapshot saved")

        stage = "report"
        result = analyze(root, now=snapshot_time)
        print("Current valuation (N/A means incomplete coverage):")
        print(result["current"].to_string(index=False, na_rep="N/A"))
        print("Price dates and age in days:")
        print(result["current_detail"][["category", "item_name", "price_date", "price_age_days"]]
              .to_string(index=False, na_rep="N/A"))
        print("Monthly snapshot history:")
        print(result["historical"].to_string(index=False, na_rep="N/A"))
        incomplete = result["current"].total_value.isna().any()
        status = PARTIAL if failures or incomplete else SUCCESS
        print(f"report: {'partial' if status == PARTIAL else 'complete'}; exit={status}")
        return status
    except (OSError, ValueError, TypeError, KeyError, AttributeError, pd.errors.ParserError) as error:
        print(f"{stage}: FAILED: {error}; exit={FAILURE}")
        return FAILURE


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["home", "school"])
    parser.add_argument("--root", type=Path, default=ROOT, help="Project root containing data/processed")
    parser.add_argument("--at", help="Local timestamp override for reproducible runs (no timezone)")
    args = parser.parse_args(argv)
    return run(args.root, args.environment, when=args.at)


if __name__ == "__main__":
    raise SystemExit(main())
