"""Check monthly snapshot persistence using temporary files only."""

from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from analyze_drop_cases import (
    calculate_historical_portfolio_value,
    save_monthly_inventory_snapshot,
)


class MonthlySnapshotTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "history.csv"

    def read_history(self):
        return pd.read_csv(self.path, parse_dates=["snapshot_date"])

    def test_first_snapshot_creates_history_without_changing_inventory(self):
        inventory = pd.DataFrame({"case_name": ["Beta", "Alpha"], "quantity": [2, 3]})
        original = inventory.copy(deep=True)

        result = save_monthly_inventory_snapshot(inventory, "2026-10-27 14:30", self.path)

        expected = pd.DataFrame({
            "snapshot_date": pd.to_datetime(["2026-10-27", "2026-10-27"]),
            "case_name": ["Alpha", "Beta"], "quantity": [3, 2],
        })
        pd.testing.assert_frame_equal(self.read_history(), expected)
        pd.testing.assert_frame_equal(result.reset_index(drop=True), expected)
        pd.testing.assert_frame_equal(inventory, original)

    def test_replacing_month_preserves_other_months_and_same_month_in_other_year(self):
        self.path.write_text(
            "snapshot_date,case_name,quantity\n"
            "2025-10-01,Alpha,1\n"
            "2026-09-01,Alpha,2\n"
            "2026-10-01,Alpha,3\n"
            "2026-10-01,Removed,4\n"
            "2026-11-01,Alpha,5\n",
            encoding="utf-8",
        )
        before = self.read_history()
        inventory = pd.DataFrame({"case_name": ["Alpha", "Added"], "quantity": [7, 8]})

        save_monthly_inventory_snapshot(inventory, "2026-10-27", self.path)
        after = self.read_history()

        current = after.loc[after.snapshot_date == pd.Timestamp("2026-10-27")]
        self.assertEqual(dict(zip(current.case_name, current.quantity)), {"Alpha": 7, "Added": 8})
        self.assertNotIn("Removed", after.case_name.tolist())
        before_other = before.loc[before.snapshot_date != pd.Timestamp("2026-10-01")]
        after_other = after.loc[after.snapshot_date != pd.Timestamp("2026-10-27")]
        pd.testing.assert_frame_equal(
            before_other.reset_index(drop=True), after_other.reset_index(drop=True)
        )

    def test_identical_rerun_does_not_duplicate_or_change_saved_snapshot(self):
        inventory = pd.DataFrame({"case_name": ["Alpha"], "quantity": [3]})
        save_monthly_inventory_snapshot(inventory, "2026-10-27", self.path)
        original_contents = self.path.read_bytes()

        save_monthly_inventory_snapshot(inventory, "2026-10-27", self.path)

        self.assertEqual(self.path.read_bytes(), original_contents)
        self.assertEqual(len(self.read_history()), 1)

    def test_saved_snapshots_keep_their_own_holdings_when_valued(self):
        save_monthly_inventory_snapshot(
            pd.DataFrame({"case_name": ["Alpha", "Beta"], "quantity": [2, 3]}),
            "2026-09-01", self.path,
        )
        save_monthly_inventory_snapshot(
            pd.DataFrame({"case_name": ["Alpha", "Gamma"], "quantity": [5, 1]}),
            "2026-10-01", self.path,
        )
        prices = pd.DataFrame({
            "date": ["2026-09-01", "2026-09-01", "2026-10-01", "2026-10-01"],
            "case_name": ["Alpha", "Beta", "Alpha", "Gamma"],
            "unit_price": [4.0, 2.0, 6.0, 10.0],
        })

        history = calculate_historical_portfolio_value(self.read_history(), prices)

        self.assertEqual(history.total_value.tolist(), [14.0, 40.0])
        self.assertEqual(history.cases_without_price.tolist(), [0, 0])


if __name__ == "__main__":
    unittest.main()
