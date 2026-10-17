"""Calculate the current market value of the drop-case inventory."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = PROJECT_ROOT / "data" / "processed" / "drop_cases_inventory.csv"
PRICE_HISTORY_PATH = PROJECT_ROOT / "data" / "processed" / "drop_cases_prices.csv"
INVENTORY_HISTORY_PATH = PROJECT_ROOT / "data" / "processed" / "drop_cases_inventory_history.csv"


def calculate_inventory_value(
    inventory: pd.DataFrame, price_history: pd.DataFrame
) -> pd.DataFrame:
    """Join each case to its latest valid price and calculate its value."""
    prices = price_history.copy()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    prices["unit_price"] = pd.to_numeric(prices["unit_price"], errors="coerce")
    prices = (
        prices.dropna(subset=["date", "unit_price"])
        .sort_values("date", kind="stable")
        .drop_duplicates(["case_name", "date"], keep="last")
    )

    latest_prices = (
        prices.sort_values("date", kind="stable")
        .drop_duplicates(subset="case_name", keep="last")
        .rename(columns={"date": "price_date", "unit_price": "unit_price"})
    )

    result = inventory.copy()
    result["quantity"] = pd.to_numeric(result["quantity"], errors="raise")
    result = result.merge(
        latest_prices[["case_name", "price_date", "unit_price"]],
        on="case_name",
        how="left",
        validate="one_to_one",
    )
    result["market_value"] = result["quantity"] * result["unit_price"]
    return result


def save_monthly_inventory_snapshot(
    inventory: pd.DataFrame,
    snapshot_date: str | pd.Timestamp,
    history_path: Path = INVENTORY_HISTORY_PATH,
) -> pd.DataFrame:
    """Save one inventory snapshot per month, replacing that month's prior snapshot."""
    snapshot_date = pd.Timestamp(snapshot_date).normalize()
    snapshot = inventory[["case_name", "quantity"]].copy()
    snapshot["quantity"] = pd.to_numeric(snapshot["quantity"], errors="raise")
    snapshot.insert(0, "snapshot_date", snapshot_date)

    if history_path.exists():
        history = pd.read_csv(history_path, parse_dates=["snapshot_date"])
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
    snapshots = inventory_history.copy()
    snapshots["snapshot_date"] = pd.to_datetime(snapshots["snapshot_date"], errors="coerce")
    snapshots["quantity"] = pd.to_numeric(snapshots["quantity"], errors="coerce")

    prices = price_history.copy()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    prices["unit_price"] = pd.to_numeric(prices["unit_price"], errors="coerce")
    prices = (
        prices.dropna(subset=["date", "unit_price"])
        .sort_values("date", kind="stable")
        .drop_duplicates(["case_name", "date"], keep="last")
    )

    valued_snapshots = []
    for case_name, case_snapshots in snapshots.groupby("case_name"):
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
        return pd.DataFrame(columns=["snapshot_date", "total_value", "cases_without_price"])

    details = pd.concat(valued_snapshots, ignore_index=True)
    totals = details.groupby("snapshot_date").agg(
        total_value=("market_value", lambda values: values.sum(min_count=1)),
        cases_without_price=("unit_price", lambda values: int(values.isna().sum())),
    )
    return totals.reset_index().sort_values("snapshot_date")


def main() -> None:
    inventory = pd.read_csv(INVENTORY_PATH)
    price_history = pd.read_csv(PRICE_HISTORY_PATH)
    valuation = calculate_inventory_value(inventory, price_history)

    print(valuation.to_string(index=False, na_rep="N/A"))
    total = valuation["market_value"].sum(min_count=1)
    if pd.isna(total):
        print("\nTotal inventory value: unavailable (no valid prices)")
    else:
        print(f"\nTotal inventory value: {total:,.2f} EUR")

    missing = valuation.loc[valuation["unit_price"].isna(), "case_name"].tolist()
    if missing:
        print("Cases without a valid price: " + ", ".join(missing))


if __name__ == "__main__":
    main()
