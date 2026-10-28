"""Read-only analyses shared by the category notebooks."""

import pandas as pd

from analyze_drop_cases import calculate_inventory_value, prepare_price_history, summarize_inventory_value


def split_price_records(prices):
    """Separate acquisition references before any market-price deduplication."""
    if "source_column" not in prices:
        mask = pd.Series(False, index=prices.index)
    else:
        columns = pd.to_numeric(prices.source_column, errors="raise")
        if columns.isna().any() or (columns < 0).any() or (columns % 1 != 0).any():
            raise ValueError("source_column must contain nonnegative whole numbers")
        mask = columns.eq(0)
    acquisitions = prices.loc[mask].copy()
    acquisitions["date"] = pd.to_datetime(acquisitions.date, errors="raise")
    acquisitions["unit_price"] = pd.to_numeric(acquisitions.unit_price, errors="raise")
    return prices.loc[~mask].copy(), acquisitions.sort_values(["item_name", "date"])


def category_price_figures(prices, acquisitions):
    """Show reference values as separate crosses, never as market line points."""
    import plotly.express as px
    import plotly.graph_objects as go

    hover = ["date_estimated"] if "date_estimated" in prices else None
    absolute = px.line(prices, x="date", y="unit_price", color="item_name", markers=True,
                       hover_data=hover, title="Prix de marche et references d'acquisition (EUR)")
    relative = px.line(prices, x="date", y="index_100", color="item_name", markers=True,
                       hover_data=hover, title="Base 100 au premier releve de marche (hors acquisitions)")
    for name, group in acquisitions.groupby("item_name"):
        absolute.add_trace(go.Scatter(
            x=group.date, y=group.unit_price, mode="markers",
            marker={"symbol": "x", "size": 12}, name=f"Acquisition : {name}",
            hovertemplate="%{x|%Y-%m-%d}<br>Reference : %{y} EUR<br>Prix d'achat non confirme<extra>%{fullData.name}</extra>",
        ))
    return absolute, relative


def analyze_category(inventory, prices):
    """Keep unknown quantities visible and exclude them from valuation."""
    prices, _ = split_price_records(prices)
    prices = prices.rename(columns={"item_name": "case_name"})
    prices = prepare_price_history(prices).dropna(subset=["unit_price"])
    inventory = inventory.copy()
    inventory["quantity"] = pd.to_numeric(inventory["quantity"], errors="raise")
    unknown = inventory.loc[inventory.quantity.isna()].copy()
    known = inventory.loc[inventory.quantity.notna()].rename(columns={"item_name": "case_name"})
    valuation = calculate_inventory_value(known, prices)
    summary = summarize_inventory_value(valuation)
    summary = {key.replace("cases", "items"): value for key, value in summary.items()}
    summary["items_without_quantity"] = len(unknown)
    if not unknown.empty:
        summary["total_value"] = float("nan")
    valuation = valuation.rename(columns={"case_name": "item_name"})
    prices = prices.rename(columns={"case_name": "item_name"}).sort_values(["item_name", "date"])
    first = prices.groupby("item_name")["unit_price"].transform("first")
    prices["index_100"] = prices.unit_price.div(first.where(first.ne(0))).mul(100)
    coverage = prices.groupby("item_name").agg(
        first_date=("date", "min"), last_date=("date", "max"), observations=("unit_price", "size")
    )
    valuation["purchase_unit_price"] = pd.to_numeric(valuation["purchase_unit_price"], errors="raise")
    valuation["purchase_cost"] = valuation.quantity * valuation.purchase_unit_price
    valuation["unrealized_change"] = valuation.market_value - valuation.purchase_cost
    return prices, valuation, unknown, coverage, summary
