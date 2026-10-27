"""Check monthly snapshot persistence using temporary files only."""

from pathlib import Path
import sys
import tempfile
import unittest
import json
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import Mock

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from analyze_drop_cases import (
    calculate_historical_portfolio_value,
    prepare_inventory,
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

    def test_empty_snapshot_roundtrip_and_monthly_replacement(self):
        holdings = pd.DataFrame({"case_name": ["Alpha"], "quantity": [2]})
        empty = pd.DataFrame(columns=["case_name", "quantity"])
        save_monthly_inventory_snapshot(holdings, "2026-09-01", self.path)
        save_monthly_inventory_snapshot(holdings, "2026-10-01", self.path)
        save_monthly_inventory_snapshot(empty, "2026-10-27", self.path)
        original = self.path.read_bytes()
        save_monthly_inventory_snapshot(empty, "2026-10-27", self.path)
        self.assertEqual(self.path.read_bytes(), original)
        snapshots = prepare_inventory(self.read_history(), historical=True)
        self.assertEqual(snapshots.snapshot_date.dt.month.tolist(), [9, 10])
        self.assertEqual(snapshots.snapshot_empty.tolist(), [False, True])
        self.assertTrue(pd.isna(snapshots.iloc[-1].case_name))
        prices = pd.DataFrame({"date": ["2026-09-01"], "case_name": ["Alpha"], "unit_price": [4.0]})
        valued = calculate_historical_portfolio_value(snapshots, prices)
        self.assertEqual(valued.total_value.tolist(), [8.0, 0.0])
        self.assertEqual(valued.total_cases.tolist(), [1, 0])
        self.assertEqual(valued.cases_without_price.tolist(), [0, 0])

        # The notebook must retain the empty month as a complete zero valuation.
        notebook = json.loads((Path(__file__).resolve().parents[1] / "notebook/analysis.ipynb").read_text(encoding="utf-8"))
        import numpy as np
        from analyze_drop_cases import summarize_inventory_value
        scope = {"pd": pd, "np": np, "snapshots": snapshots, "prices": prices.assign(date=pd.to_datetime(prices.date)),
                 "summarize_inventory_value": summarize_inventory_value, "display": Mock(), "px": Mock()}
        with redirect_stdout(StringIO()):
            exec("".join(notebook["cells"][18]["source"]), scope)
        self.assertEqual(scope["portfolio_history"].total_value.tolist(), [8.0, 0.0])
        self.assertEqual(scope["portfolio_history"].quantity_coverage_pct.tolist(), [100.0, 100.0])
        self.assertEqual(scope["portfolio_history"].change_pct.iloc[-1], -100.0)
        with redirect_stdout(StringIO()):
            exec("".join(notebook["cells"][20]["source"]), scope)
        self.assertEqual(scope["decomposition"].case_name.tolist(), ["Alpha"])

        save_monthly_inventory_snapshot(holdings, "2026-10-28", self.path)
        restored = prepare_inventory(self.read_history(), historical=True)
        self.assertFalse(restored.snapshot_empty.any())
        self.assertEqual(restored.quantity.tolist(), [2, 2])

    def test_first_empty_snapshot_has_zero_value_without_prices(self):
        save_monthly_inventory_snapshot(pd.DataFrame(columns=["case_name", "quantity"]), "2026-10-27", self.path)
        prices = pd.DataFrame(columns=["date", "case_name", "unit_price"])
        result = calculate_historical_portfolio_value(self.read_history(), prices)
        self.assertEqual(result.total_value.tolist(), [0.0])
        self.assertEqual(result.known_value.tolist(), [0.0])
        self.assertEqual(result.total_cases.tolist(), [0])

    def test_malformed_empty_markers_are_rejected(self):
        marker = pd.DataFrame({"snapshot_date": ["2026-10-27"], "case_name": [None], "quantity": [0], "snapshot_empty": [True]})
        for frame in (marker.assign(quantity=1), marker.assign(case_name="Alpha"),
                      marker.assign(snapshot_empty="True"), marker.assign(snapshot_empty=None),
                      pd.concat([marker, marker.assign(case_name="Alpha", snapshot_empty=False)]),
                      pd.concat([marker, marker])):
            with self.subTest(frame=frame), self.assertRaises(ValueError):
                prepare_inventory(frame, historical=True)


if __name__ == "__main__":
    unittest.main()
