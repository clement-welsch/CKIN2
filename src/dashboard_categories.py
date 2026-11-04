"""Read-only category presentation using the notebooks' shared market functions."""

from pathlib import Path

import pandas as pd
import plotly.express as px

from analyze_categories import category_price_figures, prepare_category_prices, split_price_records
from portfolio_data import CATEGORIES, FILES, _parse_dates, _parse_numbers, identity

LABELS = {"all": "Toutes les catégories", "case": "Caisses", "skin": "Skins",
          "souvenir": "Souvenirs", "sticker": "Stickers", "agent": "Agents", "charm": "Charms"}
ACQUISITIONS = ["date", "item_id", "category", "item_name", "unit_price"]


def acquisition_references(root, registry, cutoff, start=None):
    """References remain separate from observed prices and confirmed costs."""
    frames = []
    others = registry.loc[registry.category.isin(["sticker", "agent", "charm"]), ["item_name", "category"]].drop_duplicates()
    if others.item_name.duplicated().any():
        raise ValueError("Ambiguous acquisition category")
    names = others.set_index("item_name").category.to_dict()
    for prefix, category in FILES.items():
        path = Path(root) / "data/processed" / f"{prefix}_prices.csv"
        if not path.exists():
            continue
        raw = pd.read_csv(path).rename(columns={"case_name": "item_name"})
        _, references = split_price_records(raw)
        if references.empty:
            continue
        references["date"] = _parse_dates(references.date, "acquisition reference date")
        references["unit_price"] = _parse_numbers(references.unit_price, "acquisition reference value")
        references = references.loc[references.date.le(cutoff)]
        if start is not None:
            references = references.loc[references.date.ge(start)]
        references["category"] = category if category else references.item_name.map(names)
        if references.category.isna().any():
            raise ValueError("Cannot classify an acquisition reference without catalog metadata")
        references["item_id"] = [identity(c, n) for c, n in zip(references.category, references.item_name)]
        frames.append(references[ACQUISITIONS])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=ACQUISITIONS)


def category_data(root, data, start=None):
    rows = []
    references = acquisition_references(root, data["registry"], data["cutoff"], start)
    if data["selected_item_id"]:
        references = references.loc[references.item_id.eq(data["selected_item_id"])]
    for category in CATEGORIES:
        if category not in data["categories"]:
            continue
        market = data["prices"].loc[data["prices"].category.eq(category)]
        if data["selected_item_id"]:
            market = market.loc[market.item_id.eq(data["selected_item_id"])]
        # This is the exact normalization/index function used by category notebooks.
        series = prepare_category_prices(market, keep_missing=True)
        series["base_date"] = series.groupby("item_id").date.transform("first")
        if start is not None:
            series = series.loc[series.date.ge(start)]
        coverage = series.loc[series.unit_price.notna()].groupby(["item_id", "item_name"], as_index=False).agg(
            first_date=("date", "min"), last_date=("date", "max"), observations=("unit_price", "size"))
        holdings = data["detail"].loc[data["detail"].category.eq(category) & data["detail"].state.eq("holdings")]
        summary = data["current"].loc[data["current"].category.eq(category)]
        rows.append(dict(category=category, holdings=holdings, summary=summary, prices=series, coverage=coverage,
                         acquisitions=references.loc[references.category.eq(category)]))
    return rows


def figure_html(figure):
    figure.update_traces(connectgaps=False, selector=dict(type="scatter"))
    figure.update_layout(template="plotly_dark", paper_bgcolor="#17202b", plot_bgcolor="#17202b",
                         margin=dict(l=40, r=20, t=65, b=40), autosize=True)
    return figure.to_html(full_html=False, include_plotlyjs=False,
                          config={"responsive": True, "displayModeBar": False, "displaylogo": False})


def category_figures(category):
    absolute, relative = category_price_figures(category["prices"], category["acquisitions"])
    return [figure_html(absolute), figure_html(relative)]


def value_distribution(holdings):
    known = holdings.loc[holdings.market_value.notna() & holdings.quantity.gt(0)]
    if known.empty:
        return ""
    return figure_html(px.bar(known, x="item_name", y="market_value",
                              title="Contribution à la valeur connue (EUR)",
                              labels={"item_name": "Objet", "market_value": "Valeur connue (EUR)"}))
