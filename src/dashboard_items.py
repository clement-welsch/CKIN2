"""Exact item identity, local metadata and read-only detailed market analysis."""

import json
from pathlib import Path

import pandas as pd

from analyze_categories import prepare_category_prices
from dashboard_categories import acquisition_references
from global_snapshots import build_snapshot, value_snapshots
from market_universe import load_release, timestamp
from portfolio_data import CATEGORIES, FILES, HOLDINGS, PRICES, _parse_dates, _parse_numbers, identity, validate_prices
from update_market_prices import validate_catalog

KEYS = ["item_id", "category", "item_name"]


def item_registry(root, known, prices, cutoff):
    """Owned/history/priced/catalog identities; future releases stay unavailable."""
    root = Path(root)
    frames = [known[KEYS], prices[KEYS]]
    catalog_path = root / "data/processed/market_catalog.csv"
    if catalog_path.exists():
        catalog = pd.read_csv(catalog_path)
        validate_catalog(catalog, catalog.assign(quantity=0)[HOLDINGS])
        frames.append(catalog.assign(metadata_source="Reviewed local catalog", metadata_revision=None))
    for path in sorted((root / "data/market/releases").glob("*.json")):
        header = json.loads(path.read_text(encoding="utf-8"))
        if timestamp(header["collected_at"]) > cutoff:
            continue
        release, catalog = load_release(root, path.stem, cutoff)
        frames.append(catalog.assign(metadata_source=release["source_url"],
                                     metadata_revision=release["source_revision"], metadata_collected_at=release["collected_at"]))
    # Most recent eligible release metadata overrides earlier metadata, without
    # merging wear/StatTrak variants or inventing fields from a display name.
    return pd.concat(frames, ignore_index=True).groupby("item_id", sort=False, as_index=False).last()


def independent_prices(root, cutoff):
    path = Path(root) / "data/market/observations.csv"
    if not path.exists():
        return validate_prices(pd.DataFrame(columns=PRICES))
    prices = validate_prices(pd.read_csv(path))
    return prices.loc[prices.date.le(cutoff)]


def purchase_metadata(root, item):
    """Read explicit CSV purchase fields only; never infer costs from references."""
    result = dict(purchase_unit_price=float("nan"), purchase_date=pd.NaT)
    for prefix, category in FILES.items():
        if category is not None and category != item["category"]:
            continue
        if category is None and item["category"] not in ("sticker", "agent", "charm"):
            continue
        path = Path(root) / "data/processed" / f"{prefix}_inventory.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path).rename(columns={"case_name": "item_name"})
        selected = frame.loc[frame.item_name.eq(item["item_name"])]
        if category is None:
            selected = selected.loc[selected.item_type.eq(item["category"])]
        if len(selected) > 1:
            raise ValueError("Duplicate purchase metadata for an item")
        if selected.empty:
            continue
        row = selected.iloc[0]
        if "purchase_unit_price" in row:
            result["purchase_unit_price"] = _parse_numbers(pd.Series([row.purchase_unit_price]), "purchase unit price").iloc[0]
        if "purchase_date" in row and pd.notna(row.purchase_date):
            result["purchase_date"] = _parse_dates(pd.Series([row.purchase_date]), "purchase date").iloc[0]
    return result


def item_details(root, data, item_id, start=None):
    selected = data["registry"].loc[data["registry"].item_id.eq(item_id)]
    if len(selected) != 1:
        raise ValueError("Select one known exact item identity")
    item = selected.iloc[0].to_dict()
    combined = pd.concat([data["prices"], independent_prices(root, data["cutoff"])], ignore_index=True)
    prices = combined.loc[combined.item_id.eq(item_id)]
    series = prepare_category_prices(prices, keep_missing=True)
    # Keep the base outside a visible subperiod: changing display start is not
    # a rebase. Explicit missing observations remain gaps.
    base = series.loc[series.unit_price.notna(), "date"].min()
    visible = series.loc[series.date.ge(start)] if start is not None else series
    references = acquisition_references(root, data["registry"], data["cutoff"], start)
    references = references.loc[references.item_id.eq(item_id)]
    held = data["detail"].loc[data["detail"].state.eq("holdings") & data["detail"].item_id.eq(item_id), HOLDINGS]
    # Reuse the shared valuation and coverage contract, including zero/unknown
    # quantities, for the full local price history shown on this page.
    valuation = pd.DataFrame()
    summary = pd.DataFrame()
    if not held.empty:
        snapshots = build_snapshot(held, set(CATEGORIES), data["detail"].snapshot_date.iloc[0])
        valuation, summary = value_snapshots(snapshots, prices)
        valuation = valuation.loc[valuation.state.eq("holdings")]
        summary = summary.loc[summary.category.eq(item["category"])]
    metadata = purchase_metadata(root, item)
    if pd.notna(metadata["purchase_date"]) and metadata["purchase_date"] > data["cutoff"]:
        metadata = dict(purchase_unit_price=float("nan"), purchase_date=pd.NaT)
    # CSV unit costs do not establish a FIFO basis for current mixed lots.
    # The FIFO report is the sole source for gains and remaining cost.
    gains = data["pnl"].loc[data["pnl"].item_id.eq(item_id)] if "item_id" in data["pnl"] else pd.DataFrame()
    observed = series.loc[series.unit_price.notna()]
    latest = observed.iloc[-1] if len(observed) else None
    return dict(item=item, prices=visible, acquisitions=references, valuation=valuation, summary=summary,
                purchase_metadata=metadata, gains=gains, held=not held.empty,
                historical_mode=data["historical_mode"], base_date=base, observations=len(observed),
                latest_price=latest.unit_price if latest is not None else float("nan"),
                latest_date=latest.date if latest is not None else pd.NaT,
                age_days=(data["cutoff"]-latest.date).total_seconds()/86400 if latest is not None else float("nan"))
