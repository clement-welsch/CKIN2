"""Atomic monthly snapshots and backward-only valuation across all categories."""

import argparse

import pandas as pd

from portfolio_data import (CATEGORIES, HOLDINGS, ROOT, _parse_dates, atomic_csv,
                            load_holdings, load_prices, validate_holdings, validate_prices)

COLUMNS = ["snapshot_date", "category", "state", "item_id", "item_name", "quantity"]


def validate_snapshots(frame):
    if not set(COLUMNS).issubset(frame):
        raise ValueError("Missing global snapshot columns")
    result = frame[COLUMNS].copy()
    result["snapshot_date"] = _parse_dates(result.snapshot_date, "snapshot_date")
    for (_, category), group in result.groupby(["snapshot_date", "category"], dropna=False):
        if category not in CATEGORIES:
            raise ValueError("Unknown snapshot category")
        if group.state.eq("holdings").all():
            validate_holdings(group[HOLDINGS])
        elif len(group) == 1 and group.state.iloc[0] in ("empty", "not_imported"):
            row = group.iloc[0]
            if pd.notna(row.item_id) or pd.notna(row.item_name) or row.quantity != 0:
                raise ValueError("Category markers require absent identity and zero quantity")
        else:
            raise ValueError("Mixed or invalid category states")
    for _, group in result.groupby("snapshot_date"):
        if set(group.category) != set(CATEGORIES):
            raise ValueError("Every global snapshot must explicitly represent all six categories")
    monthly = result[["snapshot_date"]].drop_duplicates().snapshot_date.dt.to_period("M")
    if monthly.duplicated().any():
        raise ValueError("Multiple snapshots in one month")
    return result


def build_snapshot(holdings, imported, when):
    holdings = validate_holdings(holdings)
    if not set(imported).issubset(CATEGORIES) or not set(holdings.category).issubset(imported):
        raise ValueError("Holdings must belong to imported categories")
    stamp = _parse_dates(pd.Series([when]), "snapshot_date").iloc[0].normalize()
    rows = []
    for category in CATEGORIES:
        group = holdings.loc[holdings.category.eq(category)]
        if group.empty:
            rows.append(dict(snapshot_date=stamp, category=category,
                             state="empty" if category in imported else "not_imported",
                             item_id=None, item_name=None, quantity=0))
        else:
            rows.extend(dict(snapshot_date=stamp, state="holdings", **row) for row in group.to_dict("records"))
    return validate_snapshots(pd.DataFrame(rows, columns=COLUMNS))


def save_snapshot(holdings, imported, when, path):
    snapshot = build_snapshot(holdings, imported, when)
    if path.exists():
        previous = validate_snapshots(pd.read_csv(path))
        month = snapshot.snapshot_date.iloc[0].to_period("M")
        previous = previous.loc[previous.snapshot_date.dt.to_period("M").ne(month)]
        snapshot = pd.concat([previous, snapshot], ignore_index=True)
    result = validate_snapshots(snapshot).sort_values(["snapshot_date", "category", "item_id"], kind="stable").reset_index(drop=True)
    atomic_csv(result, path)
    return result


def value_snapshots(snapshots, prices):
    snapshots, prices = validate_snapshots(snapshots), validate_prices(prices)
    prices = prices.dropna(subset=["unit_price"]).sort_values("date", kind="stable")
    prices = prices.drop_duplicates(["item_id", "date"], keep="last")
    details = []
    for row in snapshots.to_dict("records"):
        eligible = prices.loc[prices.item_id.eq(row["item_id"]) & prices.date.le(row["snapshot_date"])]
        price = eligible.iloc[-1] if len(eligible) else None
        quantity = row["quantity"]
        value = (0.0 if row["state"] == "empty" or (pd.notna(quantity) and quantity == 0)
                 else quantity * price.unit_price if price is not None and pd.notna(quantity) else float("nan"))
        details.append(dict(**row, price_date=price.date if price is not None else pd.NaT,
                            unit_price=price.unit_price if price is not None else float("nan"), market_value=value,
                            price_age_days=(row["snapshot_date"]-price.date).total_seconds()/86400 if price is not None else float("nan")))
    detail = pd.DataFrame(details, columns=[*COLUMNS, "price_date", "unit_price", "market_value", "price_age_days"])
    summaries = []
    for stamp, group in detail.groupby("snapshot_date"):
        for category in [*CATEGORIES, "global"]:
            subset = group if category == "global" else group.loc[group.category.eq(category)]
            held = subset.loc[subset.state.eq("holdings") & (subset.quantity.isna() | subset.quantity.ne(0))]
            missing_quantity = int(held.quantity.isna().sum())
            missing_price = int(held.unit_price.isna().sum())
            unavailable_categories = int(subset.loc[subset.state.eq("not_imported"), "category"].nunique())
            known = float(held.market_value.sum(min_count=1)) if len(held) else (float("nan") if unavailable_categories else 0.0)
            complete = not (missing_quantity or missing_price or unavailable_categories)
            summaries.append(dict(snapshot_date=stamp, category=category, known_value=known,
                                  total_value=known if complete else float("nan"), priced_items=int(held.unit_price.notna().sum()),
                                  held_items=len(held), unknown_quantities=missing_quantity, missing_prices=missing_price,
                                  categories_not_imported=unavailable_categories, oldest_price_age_days=subset.price_age_days.max()))
    return detail, pd.DataFrame(summaries, columns=["snapshot_date", "category", "known_value", "total_value", "priced_items", "held_items", "unknown_quantities", "missing_prices", "categories_not_imported", "oldest_price_age_days"])


def report(root=ROOT, environment="school", when=None):
    if environment not in ("school", "home"):
        raise ValueError("Unknown environment")
    holdings, imported = load_holdings(root)
    when = when if when is not None else pd.Timestamp.today()
    path = root / "data/processed/global_inventory_history.csv"
    if environment == "home":
        history = save_snapshot(holdings, imported, when, path)
    else:
        history = validate_snapshots(pd.read_csv(path)) if path.exists() else pd.DataFrame(columns=COLUMNS)
    result = value_snapshots(history, load_prices(root, holdings))
    print(result[1].to_string(index=False, na_rep="N/A"))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["home", "school"])
    report(environment=parser.parse_args().environment)
