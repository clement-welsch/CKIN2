"""Regression coverage for market duplicates and acquisition CSV markers."""

from pathlib import Path
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from analyze_categories import analyze_category, category_price_figures


class MarketDuplicateTests(unittest.TestCase):
    def test_last_valid_daily_price_drives_indices_coverage_and_valuation(self):
        inventory = pd.DataFrame({
            "item_name": ["A", "B"], "item_type": ["skin", "skin"],
            "quantity": [2, 1], "purchase_unit_price": [None, None],
            "purchase_date": [None, None],
        })
        records = pd.DataFrame({
            "date": ["2026-02-01", "2026-01-01", "2026-01-01", "2026-01-01", "2026-01-01"],
            "item_name": ["A", "A", "A", "A", "B"],
            "unit_price": [20, 5, 10, None, 3],
            "source_column": [5, 3, 4, 6, 3],
            "date_estimated": [False, True, False, False, False],
        })
        original = records.copy(deep=True)
        with self.assertWarnsRegex(UserWarning, "Conflicting prices"):
            prices, valuation, _, coverage, summary = analyze_category(inventory, records)
        item = prices.loc[prices.item_name.eq("A")]
        self.assertEqual(item.unit_price.tolist(), [10, 20])
        self.assertEqual(item.index_100.tolist(), [100, 200])
        self.assertEqual(item.source_column.tolist(), [4, 5])
        self.assertEqual(coverage.loc["A", "observations"], 2)
        self.assertEqual(coverage.loc["B", "observations"], 1)
        self.assertEqual(valuation.set_index("item_name").loc["A", "market_value"], 40)
        self.assertEqual(summary["total_value"], 43)
        absolute, relative = category_price_figures(prices, records.iloc[:0])
        self.assertEqual(list(absolute.data[0].y), [10, 20])
        self.assertEqual(list(relative.data[0].y), [100, 200])
        pd.testing.assert_frame_equal(records, original)


if __name__ == "__main__":
    unittest.main()
