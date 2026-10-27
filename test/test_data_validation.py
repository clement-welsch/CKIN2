"""Validate portfolio inputs before computing or persisting holdings."""

from pathlib import Path
import sys
import tempfile
import unittest
import warnings

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from analyze_drop_cases import (
    calculate_inventory_value,
    calculate_historical_portfolio_value,
    prepare_inventory,
    prepare_price_history,
    save_monthly_inventory_snapshot,
)


class DataValidationTests(unittest.TestCase):
    def setUp(self):
        self.inventory = pd.DataFrame({"case_name": ["Alpha"], "quantity": [2]})
        self.prices = pd.DataFrame({
            "case_name": ["Alpha"], "date": ["2026-01-01"], "unit_price": [4.0],
        })
        self.history = self.inventory.assign(snapshot_date="2026-02-01")

    def test_invalid_quantities_rejected_in_current_and_historical_valuations(self):
        for value in (-1, 1.5, float("inf"), float("-inf"), None, "oops", True):
            for historical in (False, True):
                with self.subTest(value=value, historical=historical):
                    frame = (self.history if historical else self.inventory).assign(quantity=value)
                    calculate = calculate_historical_portfolio_value if historical else calculate_inventory_value
                    with self.assertRaisesRegex(ValueError, "quantity"):
                        calculate(frame, self.prices)

    def test_invalid_prices_rejected_but_missing_and_zero_prices_allowed(self):
        for value in (-1, float("inf"), float("-inf"), "oops", True):
            for calculate, frame in (
                (calculate_inventory_value, self.inventory),
                (calculate_historical_portfolio_value, self.history),
            ):
                with self.subTest(value=value, calculate=calculate.__name__):
                    with self.assertRaisesRegex(ValueError, "unit_price"):
                        calculate(frame, self.prices.assign(unit_price=value))
        missing = calculate_inventory_value(self.inventory, self.prices.assign(unit_price=None))
        self.assertTrue(missing.market_value.isna().all())
        zero = calculate_inventory_value(self.inventory, self.prices.assign(unit_price=0))
        self.assertEqual(zero.market_value.iloc[0], 0)

    def test_invalid_dates_rejected_without_dropping_rows(self):
        for value in (None, "not-a-date", "2026-02-30", 1234, "2026-01-01T00:00:00Z"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "date"):
                    prepare_price_history(self.prices.assign(date=value))
                with self.assertRaisesRegex(ValueError, "date"):
                    prepare_inventory(self.history.assign(snapshot_date=value), historical=True)

    def test_invalid_identifiers_and_missing_columns_are_explicit(self):
        for value in (None, "", "   ", " Alpha", "Alpha ", 123):
            for prepare, frame in ((prepare_inventory, self.inventory), (prepare_price_history, self.prices)):
                with self.subTest(value=value, prepare=prepare.__name__):
                    with self.assertRaisesRegex(ValueError, "case_name"):
                        prepare(frame.assign(case_name=value))
        for prepare, frame, column in (
            (prepare_inventory, self.inventory, "quantity"),
            (prepare_price_history, self.prices, "unit_price"),
        ):
            with self.assertRaisesRegex(ValueError, f"missing columns: {column}"):
                prepare(frame.drop(columns=column))

    def test_duplicate_holdings_rejected_and_distinct_names_preserved(self):
        with self.assertRaisesRegex(ValueError, "duplicate holdings"):
            prepare_inventory(pd.concat([self.inventory, self.inventory]))
        with self.assertRaisesRegex(ValueError, "duplicate holdings"):
            prepare_inventory(pd.concat([self.history, self.history]), historical=True)
        distinct = pd.DataFrame({"case_name": ["Alpha", "alpha"], "quantity": [1, 2]})
        result = calculate_inventory_value(distinct, self.prices)
        self.assertEqual(len(result), 2)
        self.assertTrue(pd.isna(result.loc[result.case_name == "alpha", "unit_price"]).all())

    def test_conflicting_prices_warn_and_keep_last_nonmissing_observation(self):
        prices = pd.concat([
            self.prices, self.prices.assign(unit_price=5), self.prices.assign(unit_price=None),
        ], ignore_index=True)
        original = prices.copy(deep=True)
        with self.assertWarnsRegex(UserWarning, "Conflicting prices"):
            result = calculate_inventory_value(self.inventory, prices)
        self.assertEqual(result.market_value.iloc[0], 10)
        pd.testing.assert_frame_equal(prices, original)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            calculate_inventory_value(self.inventory, pd.concat([self.prices, self.prices]))
        self.assertEqual(caught, [])

    def test_invalid_snapshot_does_not_overwrite_existing_history(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = Path(directory) / "history.csv"
            original = b"snapshot_date,case_name,quantity\n2026-01-01,Alpha,2\n"
            path.write_bytes(original)
            for inventory, date in (
                (self.inventory.assign(quantity=-1), "2026-02-01"),
                (self.inventory, "not-a-date"),
            ):
                with self.assertRaises(ValueError):
                    save_monthly_inventory_snapshot(inventory, date, path)
                self.assertEqual(path.read_bytes(), original)
            invalid = b"snapshot_date,case_name,quantity\n2026-01-01,Alpha,-2\n"
            path.write_bytes(invalid)
            with self.assertRaises(ValueError):
                save_monthly_inventory_snapshot(self.inventory, "2026-02-01", path)
            self.assertEqual(path.read_bytes(), invalid)

    def test_numeric_strings_are_converted_without_mutating_inputs(self):
        inventory = self.inventory.assign(quantity="2")
        prices = self.prices.assign(unit_price="4.25")
        result = calculate_inventory_value(inventory, prices)
        self.assertEqual(result.market_value.iloc[0], 8.5)
        self.assertEqual(inventory.quantity.iloc[0], "2")
        self.assertEqual(prices.unit_price.iloc[0], "4.25")


if __name__ == "__main__":
    unittest.main()
