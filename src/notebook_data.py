"""Notebook adapters over the portfolio's shared read-only analysis contract."""

import os
from pathlib import Path

import pandas as pd

from dashboard_categories import acquisition_references, category_data
from global_analysis import analyze, explain_changes, market_indices
from global_snapshots import value_snapshots
from portfolio_data import CATEGORIES, FILES, ROOT, _parse_numbers, identity
from portfolio_selection import analysis_date, selection, subset_snapshots


def notebook_context(root=ROOT):
    """Explicit data root and reproducible clock, without changing the code root."""
    return Path(os.environ.get("CKIN2_DATA_ROOT", str(root))).resolve(), analysis_date(os.environ.get("CKIN2_AS_OF"))


def category_report(root=ROOT, *, categories=CATEGORIES, as_of=None, historical=False):
    """Use dashboard selection, valuation, coverage and market normalization.

    as_of bounds prices and snapshots. historical=True selects the last recorded
    portfolio at that date; otherwise quantities are the current known portfolio.
    Neither mode treats visible public observations as owned quantities.
    """
    root, as_of = Path(root), analysis_date(as_of)
    categories = set(categories)
    if not categories or not categories.issubset(CATEGORIES):
        raise ValueError("Expected supported portfolio categories")
    data = analyze(root, now=as_of)
    detail, summary = selection(data, categories, historical=historical)
    registry = pd.concat([data["holdings"][["item_id", "category", "item_name"]],
                          data["prices"][["item_id", "category", "item_name"]],
                          data["history"].loc[data["history"].state.eq("holdings"), ["item_id", "category", "item_name"]]],
                         ignore_index=True).drop_duplicates("item_id")
    view = dict(registry=registry, cutoff=as_of, selected_item_id="", categories=categories,
                detail=detail, current=summary, prices=data["prices"])
    groups = category_data(root, view)
    prices = pd.concat([group["prices"] for group in groups], ignore_index=True)
    acquisitions = acquisition_references(root, registry, as_of)
    acquisitions = acquisitions.loc[acquisitions.category.isin(categories)]
    history = subset_snapshots(data["history"], categories, "")
    history_detail, historical_summary = value_snapshots(history, data["prices"])
    contributions = explain_changes(history, data["prices"])
    contributions = contributions.loc[contributions.category.isin(categories)]
    holdings = detail.loc[detail.state.eq("holdings")].copy()
    # Legacy declared purchase references are meaningful only for CSV holdings.
    # An owner replacement gives no evidence about the costs of its current lots.
    costs = []
    if not historical and data["provenance"]["basis"] == "manual_csv":
        for prefix, category in FILES.items():
            path = root / "data/processed" / f"{prefix}_inventory.csv"
            if not path.exists() or category == "case":
                continue
            raw = pd.read_csv(path)
            if "purchase_unit_price" not in raw:
                continue
            raw["purchase_unit_price"] = _parse_numbers(raw.purchase_unit_price, "declared purchase price")
            for row in raw.to_dict("records"):
                costs.append(dict(item_id=identity(category or row["item_type"], row["item_name"]),
                                  purchase_unit_price=row["purchase_unit_price"], purchase_date=row.get("purchase_date")))
    holdings["item_id"] = holdings.item_id.astype(object)
    holdings = holdings.merge(pd.DataFrame(costs, columns=["item_id", "purchase_unit_price", "purchase_date"]),
                              on="item_id", how="left", validate="one_to_one")
    holdings["purchase_cost"] = holdings.quantity * holdings.purchase_unit_price
    holdings["unrealized_change"] = holdings.market_value - holdings.purchase_cost
    cohort = data["holdings"].loc[data["holdings"].category.isin(categories)]
    indices, diagnostic = market_indices(cohort, data["prices"])
    return dict(data_root=str(root.resolve()), as_of=as_of, historical_mode=historical,
                provenance=(dict(basis="recorded_snapshot", source=str(root / "data/processed/global_inventory_history.csv"),
                                 collected_at=detail.snapshot_date.max()) if historical else data["provenance"]),
                holdings=holdings, detail=detail, summary=summary, prices=prices,
                acquisitions=acquisitions, groups=groups, history_detail=history_detail,
                historical=historical_summary, contributions=contributions,
                indices=indices.loc[indices.category.isin(categories)], diagnostic=diagnostic)
