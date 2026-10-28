"""Regression tests for spreadsheet layouts and incomplete category holdings."""

from pathlib import Path
import sys
import unittest
import tempfile
import csv

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from process_categories import PRICE_COLUMNS, main, number, observation_dates, preserve_acquisitions
from analyze_categories import analyze_category, category_price_figures


class CategoryTests(unittest.TestCase):
    def test_acquisitions_do_not_change_market_indices_or_valuation(self):
        inventory = pd.DataFrame({"item_name": ["A"], "item_type": ["skin"], "quantity": [2],
                                  "purchase_unit_price": [3], "purchase_date": [None]})
        records = pd.DataFrame({"date": ["2026-01-01", "2026-01-01", "2026-02-01", "2026-03-01"],
                                "item_name": ["A"] * 4, "unit_price": [100, 5, 10, 200],
                                "source_column": [0, 3, 4, 0], "date_estimated": [False] * 4})
        prices, valuation, _, coverage, _ = analyze_category(inventory, records)
        self.assertEqual(prices.index_100.tolist(), [100, 200])
        self.assertEqual(valuation.market_value.tolist(), [20])
        self.assertEqual(coverage.observations.tolist(), [2])
        from analyze_categories import split_price_records
        _, acquisitions = split_price_records(records)
        absolute, relative = category_price_figures(prices, acquisitions)
        self.assertEqual(list(absolute.data[0].y), [5, 10])
        self.assertEqual(list(absolute.data[1].y), [100, 200])
        self.assertEqual(absolute.data[1].mode, "markers")
        self.assertEqual(list(relative.data[0].y), [100, 200])
        prices, valuation, _, _, summary = analyze_category(inventory, records.loc[records.source_column.eq(0)])
        self.assertTrue(prices.empty)
        self.assertTrue(valuation.market_value.isna().all())
        self.assertTrue(pd.isna(summary["total_value"]))
        absolute, _ = category_price_figures(prices, acquisitions)
        self.assertEqual(len(absolute.data), 1)

    def test_conversion_splits_categories_and_preserves_existing_case_files(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            raw = root / "data/raw"
            target = root / "data/processed"
            raw.mkdir(parents=True)
            target.mkdir()
            fixtures = {
                "skins.csv": [["name", "qty", "purchase", "01/01/26", "unknown", "11/01/26"],
                              ["Skin", "", "2,5", "3", "4", "5"],
                              ["Charm | Test", "1", "", "3", "4", "5"]],
                "stickers.csv": [["", "", "01/01/26", "11/01/26", ""], ["Sticker", "2", "1", "2", "4"]],
                "souvenirs_cases.csv": [["", "", "", "01/01/26", ""], ["Tournament", "", "", "", ""],
                                        ["", "Map", "2", "3", "6"]],
                "drop_cases.csv": [["", "", "01/01/26", ""], ["Case", "1", "2", "2"]],
            }
            for filename, rows in fixtures.items():
                with (raw / filename).open("w", newline="", encoding="utf-8") as stream:
                    csv.writer(stream).writerows(rows)
            protected = target / "drop_cases_inventory.csv"
            protected.write_bytes(b"private newer inventory")
            main(root)
            self.assertEqual(protected.read_bytes(), b"private newer inventory")
            skins = pd.read_csv(target / "skins_inventory.csv")
            self.assertTrue(pd.isna(skins.quantity.iloc[0]))
            self.assertEqual(skins.purchase_unit_price.iloc[0], 2.5)
            others = pd.read_csv(target / "others_inventory.csv")
            self.assertEqual(set(others.item_type), {"charm", "sticker"})
            souvenirs = pd.read_csv(target / "souvenirs_inventory.csv")
            self.assertEqual(souvenirs.item_name.tolist(), ["Tournament Map Souvenir Package"])
            prices = pd.read_csv(target / "others_prices.csv")
            self.assertEqual(len(prices), 5)
            self.assertEqual(len(pd.read_csv(target / "category_import_issues.csv")), 1)
            price_path = target / "souvenirs_prices.csv"
            acquisition = ["2026-01-01", "Tournament Map Souvenir Package", "2.50", "False", "souvenirs_cases.csv", "0"]
            with price_path.open("a", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerow(acquisition)
            main(root)
            with price_path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 2)  # Same-date market price remains too.
            self.assertEqual(list(rows[0].values()), acquisition)
            first_run = price_path.read_bytes()
            main(root)
            self.assertEqual(price_path.read_bytes(), first_run)

    def test_preservation_keeps_orphan_acquisitions_and_rejects_bad_schema(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = Path(directory) / "prices.csv"
            row = ["2025-12-29", "Archived item", "3.52", "False", "souvenirs_cases.csv", "0"]
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(PRICE_COLUMNS)
                writer.writerow(row)
            self.assertEqual(list(preserve_acquisitions(path, [])[0].values()), row)
            path.write_text("unexpected,header\n", encoding="utf-8")
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                preserve_acquisitions(path, [])
            self.assertEqual(path.read_bytes(), original)

    def test_midpoint_is_marked_and_purchase_column_is_excluded(self):
        dates = observation_dates(["name", "qty", "", "01/01/2026", "Colonne 3", "11/01/2026"], 3)
        self.assertEqual(dates[4], ("2026-01-06", True))
        self.assertEqual(dates[3], ("2026-01-01", False))
        self.assertNotIn(2, dates)

    def test_sticker_totals_are_not_market_observations(self):
        dates = observation_dates(["", "", "01/01/26", "01/02/26", "", "01/03/26", ""], 2, sticker_layout=True)
        self.assertEqual(list(dates), [2, 3, 5])

    def test_numbers_preserve_missing_and_decimal_comma(self):
        self.assertEqual(number(""), "")
        self.assertEqual(number("1,25"), "1.25")
        for invalid in ("NaN", "-1", "abc"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                number(invalid)

    def test_unknown_quantity_keeps_total_unavailable(self):
        inventory = pd.DataFrame({"item_name": ["A", "B"], "item_type": ["skin", "skin"],
                                  "quantity": [2, None], "purchase_unit_price": [3, None],
                                  "purchase_date": [None, None]})
        prices = pd.DataFrame({"date": ["2026-01-01"] * 2, "item_name": ["A", "B"], "unit_price": [5, 10]})
        _, valuation, unknown, _, summary = analyze_category(inventory, prices)
        self.assertEqual(summary["known_value"], 10)
        self.assertTrue(pd.isna(summary["total_value"]))
        self.assertEqual(unknown.item_name.tolist(), ["B"])
        self.assertEqual(valuation.unrealized_change.tolist(), [4])


if __name__ == "__main__":
    unittest.main()
