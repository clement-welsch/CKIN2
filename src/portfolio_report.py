"""Update drop-case prices and report the current inventory value."""

import argparse

import pandas as pd

from analyze_drop_cases import (
    INVENTORY_PATH,
    INVENTORY_HISTORY_PATH,
    PRICE_HISTORY_PATH,
    calculate_historical_portfolio_value,
    calculate_inventory_value,
    print_inventory_value_summary,
    save_monthly_inventory_snapshot,
)
from update_drop_cases import Environment, main as update_prices


def parse_args():
    parser = argparse.ArgumentParser(
        description="Update prices and calculate the current drop-case inventory value."
    )
    parser.add_argument(
        "environment",
        choices=[environment.value for environment in Environment],
        help="Execution location: home (Steam API) or school (reuse last known price).",
    )
    return parser.parse_args()


def main(environment):
    update_prices(environment)

    inventory = pd.read_csv(INVENTORY_PATH)
    price_history = pd.read_csv(PRICE_HISTORY_PATH)
    valuation = calculate_inventory_value(inventory, price_history)

    if environment is Environment.HOME:
        inventory_history = save_monthly_inventory_snapshot(
            inventory, pd.Timestamp.today().date()
        )
    else:
        print("Mode école : tous les fichiers CSV sont utilisés en lecture seule.")
        if INVENTORY_HISTORY_PATH.exists():
            inventory_history = pd.read_csv(INVENTORY_HISTORY_PATH)
        else:
            inventory_history = pd.DataFrame(
                columns=["snapshot_date", "case_name", "quantity"]
            )
    historical_values = calculate_historical_portfolio_value(inventory_history, price_history)

    print("\nCurrent inventory valuation")
    print(valuation.to_string(index=False, na_rep="N/A"))

    print_inventory_value_summary(valuation)

    stale = valuation.loc[
        valuation["price_date"].notna()
        & (valuation["price_date"].dt.date < pd.Timestamp.today().date()),
        ["case_name", "price_date"],
    ]
    if not stale.empty:
        stale_items = ", ".join(
            f"{row.case_name} ({row.price_date:%Y-%m-%d})"
            for row in stale.itertuples(index=False)
        )
        print("No new Steam price; previous prices used for: " + stale_items)

    print(f"\nMonthly portfolio value history ({INVENTORY_HISTORY_PATH.name})")
    print(historical_values.to_string(index=False, na_rep="N/A"))


if __name__ == "__main__":
    args = parse_args()
    main(Environment(args.environment))
