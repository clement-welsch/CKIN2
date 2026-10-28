"""Price-history persistence tests with simulated Steam responses."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import update_drop_cases


class PriceHistoryTests(unittest.TestCase):
    def test_successful_updates_keep_one_header_and_all_observations(self):
        header = b"date,case_name,unit_price\n"
        old_row = b"2026-01-01,Alpha,1.25"
        for initial in (None, b"", header, header + old_row, header + old_row + b"\n"):
            with self.subTest(initial=initial), tempfile.TemporaryDirectory(
                dir=Path(__file__).parent
            ) as directory:
                root = Path(directory)
                inventory = root / "inventory.csv"
                prices = root / "prices.csv"
                inventory.write_text("case_name,quantity\nAlpha,2\n", encoding="utf-8")
                if initial is not None:
                    prices.write_bytes(initial)

                with (
                    patch.object(update_drop_cases, "INVENTORY_PATH", inventory),
                    patch.object(update_drop_cases, "PRICE_HISTORY_PATH", prices),
                    patch.object(update_drop_cases, "connect_to_steam", side_effect=[4.0, 5.0]),
                    redirect_stdout(StringIO()),
                ):
                    update_drop_cases.main(update_drop_cases.Environment.HOME)
                    update_drop_cases.main(update_drop_cases.Environment.HOME)

                result = pd.read_csv(prices)
                self.assertEqual(list(result.columns), ["date", "case_name", "unit_price"])
                expected = [1.25, 4.0, 5.0] if initial and old_row in initial else [4.0, 5.0]
                self.assertEqual(result.unit_price.tolist(), expected)
                self.assertEqual(result.case_name.tolist(), ["Alpha"] * len(expected))
                self.assertTrue(pd.to_datetime(result.date, errors="coerce").notna().all())
                self.assertEqual(prices.read_text().count(header.decode().strip()), 1)
                if initial:
                    self.assertTrue(prices.read_bytes().startswith(initial))

    def test_failed_collection_does_not_create_or_modify_history(self):
        for initial in (None, b"", b"date,case_name,unit_price\n2026-01-01,Alpha,1.25"):
            with self.subTest(initial=initial), tempfile.TemporaryDirectory(
                dir=Path(__file__).parent
            ) as directory:
                root = Path(directory)
                inventory = root / "inventory.csv"
                prices = root / "prices.csv"
                inventory.write_text("case_name,quantity\nAlpha,2\n", encoding="utf-8")
                if initial is not None:
                    prices.write_bytes(initial)
                with (
                    patch.object(update_drop_cases, "INVENTORY_PATH", inventory),
                    patch.object(update_drop_cases, "PRICE_HISTORY_PATH", prices),
                    patch.object(update_drop_cases, "connect_to_steam", return_value=None),
                    redirect_stdout(StringIO()),
                ):
                    update_drop_cases.main(update_drop_cases.Environment.HOME)
                if initial is None:
                    self.assertFalse(prices.exists())
                else:
                    self.assertEqual(prices.read_bytes(), initial)


if __name__ == "__main__":
    unittest.main()
