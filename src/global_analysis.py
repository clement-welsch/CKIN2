"""Read-only global values, comparable fixed-cohort indices and contributions."""

import pandas as pd

from global_snapshots import COLUMNS, build_snapshot, validate_snapshots, value_snapshots
from portfolio_data import CATEGORIES, ROOT, load_holdings, load_prices, validate_holdings, validate_prices

INDEX_COLUMNS = ["date", "category", "index_100", "covered_items", "cohort_items", "base_date", "oldest_price_age_days"]


def market_indices(holdings, prices, max_age_days=45):
    """Equal item weights fixed at one exact common observed base date.

    Estimated dates are excluded. Later prices can be carried backward-as-of
    at most max_age_days, with explicit coverage. No row uses a future price.
    """
    holdings, prices = validate_holdings(holdings), validate_prices(prices)
    if not isinstance(max_age_days, (int, float)) or not 0 <= max_age_days < float("inf"):
        raise ValueError("max_age_days must be finite and nonnegative")
    selected = holdings.item_id.tolist()
    market = prices.loc[~prices.date_estimated & prices.item_id.isin(selected) & prices.unit_price.notna()]
    market = market.sort_values("date", kind="stable").drop_duplicates(["item_id", "date"], keep="last")
    diagnostic = {"cohort_items": len(selected), "excluded_estimated_dates": int(prices.date_estimated.sum()),
                  "weighting": "equal weight per item; global is equal weight across all items",
                  "max_age_days": max_age_days, "reason": "", "base_date": pd.NaT}
    if not selected:
        diagnostic["reason"] = "No tracked items"
        return pd.DataFrame(columns=INDEX_COLUMNS), diagnostic
    common = None
    for item_id in selected:
        dates = set(market.loc[market.item_id.eq(item_id), "date"])
        common = dates if common is None else common & dates
    if not common:
        diagnostic["reason"] = "No exact common observed base date for the fixed cohort"
        return pd.DataFrame(columns=INDEX_COLUMNS), diagnostic
    base_date = min(common)
    base = market.loc[market.date.eq(base_date)].set_index("item_id").unit_price
    diagnostic["base_date"] = base_date
    if base.eq(0).any():
        diagnostic["reason"] = "Zero price at the common base; relative comparison unavailable"
        return pd.DataFrame(columns=INDEX_COLUMNS), diagnostic
    stamps = sorted(market.loc[market.date.ge(base_date), "date"].unique())
    rows = []
    for stamp in stamps:
        eligible = market.loc[market.date.le(stamp)].drop_duplicates("item_id", keep="last")
        detail = holdings[["item_id", "category"]].merge(eligible[["item_id", "date", "unit_price"]], on="item_id", how="left")
        detail["age"] = (stamp - detail.date).dt.total_seconds() / 86400
        detail["relative"] = detail.unit_price / detail.item_id.map(base) * 100
        detail.loc[detail.age.gt(max_age_days), "relative"] = float("nan")
        for category in [*CATEGORIES, "global"]:
            group = detail if category == "global" else detail.loc[detail.category.eq(category)]
            if group.empty:
                continue
            covered = int(group.relative.notna().sum())
            rows.append(dict(date=stamp, category=category,
                             index_100=group.relative.mean() if covered == len(group) else float("nan"),
                             covered_items=covered, cohort_items=len(group), base_date=base_date,
                             oldest_price_age_days=group.age.max()))
    return pd.DataFrame(rows, columns=INDEX_COLUMNS), diagnostic


def explain_changes(snapshots, prices):
    """Decompose covered changes: q0*(p1-p0) + (q1-q0)*p1."""
    snapshots, prices = validate_snapshots(snapshots), validate_prices(prices)
    prices = prices.dropna(subset=["unit_price"]).sort_values("date", kind="stable").drop_duplicates(["item_id", "date"], keep="last")
    stamps = sorted(snapshots.snapshot_date.unique())
    rows = []
    for start, end in zip(stamps, stamps[1:]):
        before, after = [snapshots.loc[snapshots.snapshot_date.eq(stamp)] for stamp in (start, end)]
        missing_categories = set(pd.concat([before, after]).loc[lambda f: f.state.eq("not_imported"), "category"])
        universe = pd.concat([before, after]).loc[lambda f: f.state.eq("holdings"), HOLDING_KEYS].drop_duplicates("item_id")
        for item in universe.itertuples(index=False):
            quantities = []
            matched = []
            for stamp, holdings in [(start, before), (end, after)]:
                held = holdings.loc[holdings.item_id.eq(item.item_id), "quantity"]
                quantities.append(held.iloc[0] if len(held) else 0)
                observed = prices.loc[prices.item_id.eq(item.item_id) & prices.date.le(stamp)]
                matched.append(observed.unit_price.iloc[-1] if len(observed) else float("nan"))
            q0, q1 = quantities
            p0, p1 = matched
            covered = item.category not in missing_categories and all(pd.notna(v) for v in [q0, q1, p0, p1])
            rows.append(dict(start_date=start, end_date=end, category=item.category, item_id=item.item_id,
                             item_name=item.item_name, covered=covered,
                             price_effect=q0 * (p1-p0) if covered else float("nan"),
                             quantity_effect=(q1-q0) * p1 if covered else float("nan"),
                             value_change=q1*p1-q0*p0 if covered else float("nan")))
    return pd.DataFrame(rows, columns=["start_date", "end_date", "category", "item_id", "item_name", "covered", "price_effect", "quantity_effect", "value_change"])


HOLDING_KEYS = ["item_id", "category", "item_name"]


def analyze(root=ROOT, now=None, max_age_days=45):
    holdings, imported = load_holdings(root)
    prices = load_prices(root, holdings)
    now = pd.Timestamp.now() if now is None else pd.Timestamp(now)
    # Never use future rows even if files contain them.
    prices = prices.loc[prices.date.le(now)].copy()
    current_detail, current = value_snapshots(build_snapshot(holdings, imported, now), prices)
    path = root / "data/processed/global_inventory_history.csv"
    history = validate_snapshots(pd.read_csv(path)) if path.exists() else pd.DataFrame(columns=COLUMNS)
    history = history.loc[history.snapshot_date.le(now)]
    history_detail, historical = value_snapshots(history, prices)
    provenance = (prices.dropna(subset=["unit_price"]).sort_values("date", kind="stable")
                  .drop_duplicates(["item_id", "date"], keep="last")
                  [["item_id", "date", "date_estimated", "source"]]
                  .rename(columns={"date": "price_date", "date_estimated": "price_date_estimated", "source": "price_source"}))
    current_detail["price_date"] = pd.to_datetime(current_detail.price_date)
    history_detail["price_date"] = pd.to_datetime(history_detail.price_date)
    current_detail = current_detail.merge(provenance, on=["item_id", "price_date"], how="left", validate="many_to_one")
    history_detail = history_detail.merge(provenance, on=["item_id", "price_date"], how="left", validate="many_to_one")
    indices, diagnostic = market_indices(holdings, prices, max_age_days)
    return dict(holdings=holdings, prices=prices, current_detail=current_detail, current=current,
                history=history, history_detail=history_detail, historical=historical,
                indices=indices, diagnostic=diagnostic, contributions=explain_changes(history, prices))
