"""Calculate the current market value of the drop-case inventory."""

from math import isfinite
from numbers import Number
from pathlib import Path
import warnings

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = PROJECT_ROOT / "data" / "processed" / "drop_cases_inventory.csv"
PRICE_HISTORY_PATH = PROJECT_ROOT / "data" / "processed" / "drop_cases_prices.csv"
INVENTORY_HISTORY_PATH = PROJECT_ROOT / "data" / "processed" / "drop_cases_inventory_history.csv"


def _require_columns(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{label}: missing columns: {', '.join(missing)}")


def _validate_names(frame: pd.DataFrame, label: str) -> None:
    valid = frame["case_name"].map(
        lambda name: isinstance(name, str) and bool(name.strip()) and name == name.strip()
    )
    if not valid.all():
        raise ValueError(f"{label}: case_name must be a nonempty string without surrounding whitespace")


def _parse_dates(values: pd.Series, label: str) -> pd.Series:
    def parse(value):
        if isinstance(value, (Number, bool)):
            raise ValueError(f"{label}: dates must not be numeric")
        try:
            stamp = pd.Timestamp(value)
        except (ValueError, TypeError, OverflowError) as error:
            raise ValueError(f"{label}: invalid date") from error
        if pd.isna(stamp) or stamp.tzinfo is not None:
            raise ValueError(f"{label}: dates must be present and timezone-naive")
        return stamp

    return pd.to_datetime(values.map(parse))


def _parse_numbers(values: pd.Series, label: str, *, quantity: bool = False) -> pd.Series:
    if values.map(lambda value: isinstance(value, bool)).any():
        raise ValueError(f"{label}: boolean values are not allowed")
    try:
        numbers = pd.to_numeric(values, errors="raise")
    except (ValueError, TypeError) as error:
        raise ValueError(f"{label}: expected numeric values") from error
    present = numbers.dropna()
    if not present.map(lambda value: isfinite(value) and value >= 0).all():
        raise ValueError(f"{label}: values must be finite and nonnegative")
    if quantity and (numbers.isna().any() or (present % 1 != 0).any()):
        raise ValueError(f"{label}: quantities must be present whole numbers")
    return numbers


def prepare_inventory(inventory: pd.DataFrame, *, historical: bool = False) -> pd.DataFrame:
    """Validate holdings and explicit empty-snapshot markers.

    Legacy histories need no migration. An empty snapshot is one row with
    snapshot_empty=True, a missing case_name and quantity=0. It cannot coexist
    with holdings at the same date.
    """
    label = "Inventory history" if historical else "Inventory"
    keys = ["snapshot_date", "case_name"] if historical else ["case_name"]
    _require_columns(inventory, [*keys, "quantity"], label)
    result = inventory.copy()
    empty = pd.Series(False, index=result.index)
    if historical and "snapshot_empty" in result:
        markers = result["snapshot_empty"]
        if not markers.map(lambda value: isinstance(value, bool)).all():
            raise ValueError(f"{label}: snapshot_empty must contain boolean values")
        empty = markers
    _validate_names(result.loc[~empty], label)
    result["quantity"] = _parse_numbers(result["quantity"], f"{label}.quantity", quantity=True)
    if historical:
        result["snapshot_date"] = _parse_dates(result["snapshot_date"], f"{label}.snapshot_date")
        if (empty & (result["case_name"].notna() | result["quantity"].ne(0))).any():
            raise ValueError(f"{label}: empty snapshots require missing case_name and quantity=0")
        if result.loc[empty, "snapshot_date"].isin(result.loc[~empty, "snapshot_date"]).any():
            raise ValueError(f"{label}: empty snapshots cannot contain holdings")
    if result.duplicated(keys).any():
        raise ValueError(f"{label}: duplicate holdings for {', '.join(keys)}")
    return result


def prepare_price_history(price_history: pd.DataFrame) -> pd.DataFrame:
    """Validate prices, preserving missing observations and warning on conflicts.

    Same-item, same-timestamp observations retain the last nonmissing price in
    file order. No rounding, case folding, or identifier normalization is used.
    """
    _require_columns(price_history, ["case_name", "date", "unit_price"], "Price history")
    prices = price_history.copy()
    _validate_names(prices, "Price history")
    prices["date"] = _parse_dates(prices["date"], "Price history.date")
    prices["unit_price"] = _parse_numbers(prices["unit_price"], "Price history.unit_price")
    valid = prices.dropna(subset=["unit_price"])
    conflicts = valid.groupby(["case_name", "date"])["unit_price"].nunique()
    if (conflicts > 1).any():
        warnings.warn(
            "Conflicting prices for the same case and timestamp; last nonmissing row wins.",
            UserWarning, stacklevel=2,
        )
    return prices


def calculate_inventory_value(
    inventory: pd.DataFrame, price_history: pd.DataFrame
) -> pd.DataFrame:
    """Join each case to its latest valid price and calculate its value."""
    prices = prepare_price_history(price_history).dropna(subset=["unit_price"])
    prices = prices.sort_values("date", kind="stable").drop_duplicates(["case_name", "date"], keep="last")

    latest_prices = (
        prices.sort_values("date", kind="stable")
        .drop_duplicates(subset="case_name", keep="last")
        .rename(columns={"date": "price_date", "unit_price": "unit_price"})
    )

    result = prepare_inventory(inventory)
    result = result.merge(
        latest_prices[["case_name", "price_date", "unit_price"]],
        on="case_name",
        how="left",
        validate="one_to_one",
    )
    result["market_value"] = result["quantity"] * result["unit_price"]
    return result


def summarize_inventory_value(valuation: pd.DataFrame) -> dict:
    """Separate known value from a complete total, counting only held items.

    An empty inventory has a complete value of zero. Zero-quantity rows do not
    require a price. Coverage counts item types, rather than individual units.
    """
    held = valuation.loc[valuation["quantity"] != 0]
    priced = held["market_value"].notna()
    missing = int((~priced).sum())
    known = float(held["market_value"].sum(min_count=1)) if len(held) else 0.0
    return {
        "known_value": known,
        "total_value": known if missing == 0 else float("nan"),
        "priced_cases": int(priced.sum()),
        "total_cases": len(held),
        "cases_without_price": missing,
    }


def print_inventory_value_summary(valuation: pd.DataFrame) -> None:
    """Print coverage and label a partial valuation explicitly."""
    summary = summarize_inventory_value(valuation)
    print(f"\nPrice coverage: {summary['priced_cases']}/{summary['total_cases']} held item types")
    if summary["cases_without_price"] == 0:
        print(f"Total inventory value: {summary['total_value']:,.2f} EUR")
    else:
        if pd.isna(summary["known_value"]):
            print("Known inventory value: unavailable (no valid prices)")
        else:
            print(f"Known inventory value (partial): {summary['known_value']:,.2f} EUR")
        print("Total inventory value: unavailable (incomplete price coverage)")
        missing = valuation.loc[
            (valuation["quantity"] != 0) & valuation["market_value"].isna(), "case_name"
        ].tolist()
        print("Cases without a valid price: " + ", ".join(missing))


def save_monthly_inventory_snapshot(
    inventory: pd.DataFrame,
    snapshot_date: str | pd.Timestamp,
    history_path: Path = INVENTORY_HISTORY_PATH,
) -> pd.DataFrame:
    """Save one inventory snapshot per month, replacing that month's prior snapshot."""
    snapshot_date = _parse_dates(pd.Series([snapshot_date]), "Snapshot date").iloc[0].normalize()
    snapshot = prepare_inventory(inventory)[["case_name", "quantity"]]
    snapshot.insert(0, "snapshot_date", snapshot_date)
    if snapshot.empty:
        snapshot = pd.DataFrame({
            "snapshot_date": [snapshot_date], "case_name": [None],
            "quantity": [0], "snapshot_empty": [True],
        })

    if history_path.exists():
        history = prepare_inventory(pd.read_csv(history_path), historical=True)
        if "snapshot_empty" in history or "snapshot_empty" in snapshot:
            for frame in (history, snapshot):
                if "snapshot_empty" not in frame:
                    frame["snapshot_empty"] = False
        same_month = (history["snapshot_date"].dt.year == snapshot_date.year) & (
            history["snapshot_date"].dt.month == snapshot_date.month
        )
        history = history.loc[~same_month]
        history = pd.concat([history, snapshot], ignore_index=True)
    else:
        history = snapshot

    history = history.sort_values(["snapshot_date", "case_name"])
    history.to_csv(history_path, index=False, date_format="%Y-%m-%d")
    return history


def calculate_historical_portfolio_value(
    inventory_history: pd.DataFrame, price_history: pd.DataFrame
) -> pd.DataFrame:
    """Value each monthly inventory snapshot using the latest price on or before it."""
    snapshots = prepare_inventory(inventory_history, historical=True)
    prices = prepare_price_history(price_history).dropna(subset=["unit_price"])
    prices = prices.sort_values("date", kind="stable").drop_duplicates(["case_name", "date"], keep="last")

    valued_snapshots = []
    for case_name, case_snapshots in snapshots.groupby("case_name", dropna=False):
        case_prices = prices.loc[prices["case_name"] == case_name, ["date", "unit_price"]]
        case_snapshots = case_snapshots.sort_values("snapshot_date")
        if case_prices.empty:
            case_snapshots = case_snapshots.copy()
            case_snapshots["unit_price"] = float("nan")
        else:
            case_snapshots = pd.merge_asof(
                case_snapshots,
                case_prices.sort_values("date", kind="stable"),
                left_on="snapshot_date",
                right_on="date",
                direction="backward",
            )
        case_snapshots["market_value"] = case_snapshots["quantity"] * case_snapshots["unit_price"]
        valued_snapshots.append(case_snapshots)

    if not valued_snapshots:
        return pd.DataFrame(columns=[
            "snapshot_date", "known_value", "total_value", "priced_cases",
            "total_cases", "cases_without_price",
        ])

    details = pd.concat(valued_snapshots, ignore_index=True)
    return pd.DataFrame([
        {"snapshot_date": snapshot_date, **summarize_inventory_value(group)}
        for snapshot_date, group in details.groupby("snapshot_date", sort=True)
    ])


def main() -> None:
    inventory = pd.read_csv(INVENTORY_PATH)
    price_history = pd.read_csv(PRICE_HISTORY_PATH)
    valuation = calculate_inventory_value(inventory, price_history)

    print(valuation.to_string(index=False, na_rep="N/A"))
    print_inventory_value_summary(valuation)


if __name__ == "__main__":
    main()
