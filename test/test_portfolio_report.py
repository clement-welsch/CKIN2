import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import portfolio_report
import update_drop_cases
from analyze_drop_cases import calculate_inventory_value


class PortfolioReportTests(unittest.TestCase):
    def test_school_mode_does_not_request_steam_or_change_price_history(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary_directory:
            price_history_path = Path(temporary_directory) / "prices.csv"
            original_contents = b"date,case_name,unit_price\n2026-10-17,Test Case,1.25\n"
            price_history_path.write_bytes(original_contents)

            with patch.object(update_drop_cases, "PRICE_HISTORY_PATH", price_history_path), patch.object(
                update_drop_cases,
                "connect_to_steam",
                side_effect=AssertionError("School mode must not contact Steam."),
            ):
                update_drop_cases.main(update_drop_cases.Environment.SCHOOL)

            self.assertEqual(price_history_path.read_bytes(), original_contents)

    def test_school_portfolio_report_does_not_write_any_csv(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary_directory:
            root = Path(temporary_directory)
            inventory_path = root / "inventory.csv"
            prices_path = root / "prices.csv"
            history_path = root / "inventory_history.csv"
            inventory_path.write_text("case_name,quantity\nAlpha,3\n", encoding="utf-8")
            prices_path.write_text(
                "date,case_name,unit_price\n2026-10-17,Alpha,4.00\n", encoding="utf-8"
            )
            history_path.write_text(
                "snapshot_date,case_name,quantity\n2026-09-17,Alpha,2\n",
                encoding="utf-8",
            )
            csv_contents = {
                path: path.read_bytes()
                for path in (inventory_path, prices_path, history_path)
            }

            with (
                patch.object(portfolio_report, "INVENTORY_PATH", inventory_path),
                patch.object(portfolio_report, "PRICE_HISTORY_PATH", prices_path),
                patch.object(portfolio_report, "INVENTORY_HISTORY_PATH", history_path),
                patch.object(portfolio_report, "update_prices") as update_prices,
            ):
                portfolio_report.main(update_drop_cases.Environment.SCHOOL)

            update_prices.assert_called_once_with(update_drop_cases.Environment.SCHOOL)
            for path, original_contents in csv_contents.items():
                self.assertEqual(path.read_bytes(), original_contents)

    def test_inventory_value_uses_latest_price_and_keeps_unpriced_cases(self):
        inventory = pd.DataFrame(
            {
                "case_name": ["Alpha", "Beta", "Gamma"],
                "quantity": [3, 2, 1],
            }
        )
        price_history = pd.DataFrame(
            {
                "date": ["2026-01-10", "2026-02-10", "2026-02-05"],
                "case_name": ["Alpha", "Alpha", "Beta"],
                "unit_price": [2.0, 4.0, 1.5],
            }
        )

        result = calculate_inventory_value(inventory, price_history).set_index("case_name")

        self.assertEqual(result.loc["Alpha", "unit_price"], 4.0)
        self.assertEqual(result.loc["Alpha", "market_value"], 12.0)
        self.assertEqual(result.loc["Beta", "market_value"], 3.0)
        self.assertTrue(pd.isna(result.loc["Gamma", "unit_price"]))
        self.assertTrue(pd.isna(result.loc["Gamma", "market_value"]))


if __name__ == "__main__":
    unittest.main()
