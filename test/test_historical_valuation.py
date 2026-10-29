"""Contracts for the shared historical detail and aggregate calculation."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from analyze_drop_cases import calculate_historical_portfolio_value, calculate_historical_valuation


class HistoricalValuationTests(unittest.TestCase):
    def check_consumers(self, snapshots, prices):
        original_snapshots, original_prices = snapshots.copy(deep=True), prices.copy(deep=True)
        details, summary = calculate_historical_valuation(snapshots, prices)
        console = calculate_historical_portfolio_value(snapshots, prices)
        pd.testing.assert_frame_equal(console, summary[console.columns])
        notebook = json.loads((ROOT / "notebook/cases_book.ipynb").read_text(encoding="utf-8"))
        scope = {"snapshots": snapshots, "prices": prices, "display": Mock(), "px": Mock()}
        with redirect_stdout(StringIO()):
            exec("".join(notebook["cells"][18]["source"]), scope)
        pd.testing.assert_frame_equal(scope["snapshot_details"], details)
        pd.testing.assert_frame_equal(scope["portfolio_history"][summary.columns], summary)
        pd.testing.assert_frame_equal(snapshots, original_snapshots)
        pd.testing.assert_frame_equal(prices, original_prices)
        return details, summary

    def test_complete_partial_and_future_prices_use_snapshot_holdings(self):
        snapshots = pd.DataFrame({
            "snapshot_date": ["2026-02-01", "2026-01-01", "2026-02-01", "2026-01-01"],
            "case_name": ["Alpha", "Alpha", "Gamma", "Beta"], "quantity": [5, 2, 1, 3],
        })
        prices = pd.DataFrame({
            "date": ["2026-01-01", "2026-01-01", "2026-02-01", "2026-03-01"],
            "case_name": ["Alpha", "Beta", "Alpha", "Gamma"], "unit_price": [4.0, 2.0, 6.0, 100.0],
        })
        details, summary = self.check_consumers(snapshots, prices)
        self.assertEqual(summary.known_value.tolist(), [14.0, 30.0])
        self.assertEqual(summary.total_value.iloc[0], 14.0)
        self.assertTrue(pd.isna(summary.total_value.iloc[1]))
        self.assertEqual(summary.priced_cases.tolist(), [2, 1])
        self.assertEqual(summary.total_quantity.tolist(), [5, 6])
        self.assertEqual(summary.priced_quantity.tolist(), [5, 5])
        self.assertTrue(details.loc[details.case_name.eq("Gamma"), "unit_price"].isna().all())
        self.assertTrue((details.dropna(subset=["date"]).date <= details.dropna(subset=["date"]).snapshot_date).all())

    def test_empty_history_and_explicit_empty_snapshot_have_stable_contracts(self):
        prices = pd.DataFrame(columns=["date", "case_name", "unit_price"])
        details, summary = self.check_consumers(pd.DataFrame(columns=["snapshot_date", "case_name", "quantity"]), prices)
        self.assertTrue(details.empty)
        self.assertTrue(summary.empty)
        self.assertIn("market_value", details)
        marker = pd.DataFrame({"snapshot_date": ["2026-01-01"], "case_name": [None], "quantity": [0], "snapshot_empty": [True]})
        details, summary = self.check_consumers(marker, prices)
        self.assertTrue(details.snapshot_empty.iloc[0])
        self.assertEqual(summary.total_value.tolist(), [0.0])
        self.assertEqual(summary.total_cases.tolist(), [0])

    def test_zero_quantities_missing_prices_and_zero_observation(self):
        snapshots = pd.DataFrame({"snapshot_date": ["2026-01-01"] * 3, "case_name": ["Alpha", "Beta", "Gamma"], "quantity": [2, 0, 3]})
        prices = pd.DataFrame({"date": ["2026-01-01"], "case_name": ["Alpha"], "unit_price": [0.0]})
        _, summary = self.check_consumers(snapshots, prices)
        self.assertEqual(summary.known_value.tolist(), [0.0])
        self.assertTrue(summary.total_value.isna().all())
        self.assertEqual(summary.total_cases.tolist(), [2])
        self.assertEqual(summary.priced_cases.tolist(), [1])


if __name__ == "__main__":
    unittest.main()
