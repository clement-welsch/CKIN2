"""Collect exact Steam listings across all categories; never rewrite legacy exports."""

import argparse
from datetime import datetime
from math import isfinite
import time

import pandas as pd

from portfolio_data import ROOT, HOLDINGS, PRICES, atomic_csv, load_holdings, load_prices, validate_holdings, validate_prices
from update_drop_cases import fetch_market_price

CATALOG = ["item_id", "category", "item_name", "market_hash_name"]


def catalog_template(holdings):
    result = holdings[["item_id", "category", "item_name"]].copy()
    result["market_hash_name"] = ""
    cases = result.category.eq("case")
    result.loc[cases, "market_hash_name"] = result.loc[cases, "item_name"].map(
        lambda n: n if n.endswith((" Case", " Terminal")) else n + " Case"
    )
    return result


def validate_catalog(catalog, holdings):
    if not set(CATALOG).issubset(catalog) or catalog.item_id.duplicated().any():
        raise ValueError("Catalog requires unique item_id and exact listing columns")
    validate_holdings(catalog.assign(quantity=0)[HOLDINGS])
    expected = holdings[["item_id", "category", "item_name"]]
    merged = expected.merge(catalog[CATALOG], on=["item_id", "category", "item_name"], how="left", validate="one_to_one")
    if not set(holdings.item_id).issubset(catalog.item_id):
        raise ValueError("Catalog must cover the current inventory; add and review new mappings")
    valid = merged.market_hash_name.map(lambda n: isinstance(n, str) and bool(n) and n == n.strip())
    if not valid.all() or merged.market_hash_name.duplicated().any():
        raise ValueError("Review every exact Steam market_hash_name; blanks and duplicate listings are rejected")
    return merged


def collect(root=ROOT, environment="school", *, now=None, fetch=None, pause=time.sleep):
    if environment not in ("school", "home"):
        raise ValueError("Unknown environment")
    now = pd.Timestamp(now if now is not None else datetime.now()).floor("s")
    if pd.isna(now) or now.tzinfo is not None:
        raise ValueError("Expected a local timezone-naive collection timestamp")
    holdings, _ = load_holdings(root)
    target = root / "data/processed/market_observations.csv"
    history = validate_prices(pd.read_csv(target)) if target.exists() else pd.DataFrame(columns=PRICES)
    rows, outcomes = [], {}
    if environment == "home":
        catalog = validate_catalog(pd.read_csv(root / "data/processed/market_catalog.csv"), holdings)
        fetch = fetch or fetch_market_price
        for index, row in enumerate(catalog.itertuples(index=False)):
            price = fetch(row.market_hash_name)
            if price is not None and not isinstance(price, bool) and isfinite(price) and price >= 0:
                rows.append(dict(date=now, item_id=row.item_id, category=row.category, item_name=row.item_name,
                                 unit_price=price, source="steam", currency="EUR", date_estimated=False))
                outcomes[row.item_id] = "updated"
            else:
                outcomes[row.item_id] = "failed"
            if index + 1 < len(catalog):
                pause(2)
        if rows:
            combined = pd.concat([history, pd.DataFrame(rows)], ignore_index=True)
            # One observation per item/source/timestamp; same timestamp retries replace it.
            combined = validate_prices(combined).drop_duplicates(["date", "item_id", "source"], keep="last")
            atomic_csv(combined, target)
    prices = load_prices(root, holdings)
    prices = prices.loc[prices.date.le(now) & prices.unit_price.notna()]
    latest = prices.sort_values("date", kind="stable").drop_duplicates("item_id", keep="last")
    report = holdings.merge(latest[["item_id", "date", "unit_price"]], on="item_id", how="left")
    report["outcome"] = report.item_id.map(outcomes).astype("string").fillna("saved_price_only")
    report["age_days"] = (now - report.date).dt.total_seconds() / 86400
    print(report.to_string(index=False, na_rep="N/A"))
    for category, group in report.groupby("category"):
        print(f"{category}: {group.unit_price.notna().sum()}/{len(group)} priced; "
              f"{group.outcome.eq('failed').sum()} failed; oldest price age={group.age_days.max()} days")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["home", "school"])
    parser.add_argument("--init-catalog", action="store_true", help="Write a NEW catalog template; review non-case mappings")
    args = parser.parse_args()
    if args.init_catalog:
        if args.environment != "home":
            parser.error("school is read-only")
        path = ROOT / "data/processed/market_catalog.csv"
        if path.exists():
            parser.error("Catalog already exists; preserve and edit its mappings manually")
        atomic_csv(catalog_template(load_holdings()[0]), path)
    else:
        collect(environment=args.environment)
