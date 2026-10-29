"""Regression coverage for market duplicates and acquisition CSV markers."""

from pathlib import Path
import csv
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from analyze_categories import analyze_category, category_price_figures
from process_categories import PRICE_COLUMNS, main, preserve_acquisitions


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


class AcquisitionMarkerTests(unittest.TestCase):
    def test_invalid_markers_fail_without_changing_the_source_file(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = Path(directory) / "prices.csv"
            for marker in ("", "NaN", "inf", "-1", "0.5"):
                with self.subTest(marker=marker):
                    with path.open("w", newline="", encoding="utf-8") as stream:
                        writer = csv.writer(stream)
                        writer.writerow(PRICE_COLUMNS)
                        writer.writerow(["2026-01-01", "A", "5", "False", "source.csv", marker])
                    original = path.read_bytes()
                    with self.assertRaises(ValueError):
                        preserve_acquisitions(path, [])
                    self.assertEqual(path.read_bytes(), original)

    def test_numeric_zero_markers_survive_repeated_conversion_in_all_categories(self):
        categories = ("skins", "souvenirs", "others")
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            target = root / "data/processed"
            target.mkdir(parents=True)
            manual = [dict(zip(PRICE_COLUMNS, ["2026-01-01", f"A-{marker}", "3.52", "False", "source.csv", marker]))
                      for marker in ("0", "0.0", "0.00")]
            generated = {category: [dict(zip(PRICE_COLUMNS, ["2026-01-01", "A-0.0", "5", False, "source.csv", 3]))]
                         for category in categories}
            generated["drop_cases"] = []
            for category in categories:
                with (target / f"{category}_prices.csv").open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=PRICE_COLUMNS)
                    writer.writeheader()
                    writer.writerows(manual)
            first_run = {}
            for run in range(2):
                inventories = {category: [] for category in (*categories, "drop_cases")}
                prices = {category: [row.copy() for row in rows] for category, rows in generated.items()}
                with patch("process_categories.convert", return_value=(inventories, prices, [])):
                    main(root)
                for category in categories:
                    path = target / f"{category}_prices.csv"
                    with path.open(newline="", encoding="utf-8") as stream:
                        rows = list(csv.DictReader(stream))
                    self.assertEqual(len(rows), 4)
                    self.assertEqual([r for r in rows if r["source_column"] != "3"], manual)
                    self.assertEqual(next(r for r in rows if r["source_column"] == "3")["unit_price"], "5")
                    if run == 0:
                        first_run[category] = path.read_bytes()
                    else:
                        self.assertEqual(path.read_bytes(), first_run[category])


if __name__ == "__main__":
    unittest.main()
