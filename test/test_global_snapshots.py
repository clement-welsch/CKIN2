import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from test_multicategory_prices import fixture
from portfolio_data import CATEGORIES, HOLDINGS, PRICES, identity
from global_snapshots import build_snapshot, report, save_snapshot, validate_snapshots, value_snapshots


class SnapshotTests(unittest.TestCase):
    def prices(self, holdings):
        return pd.DataFrame([dict(date="2026-01-01", item_id=r.item_id, category=r.category, item_name=r.item_name,
                                  unit_price=10, source="steam", currency="EUR", date_estimated=False)
                             for r in holdings.itertuples()], columns=PRICES)

    def test_complete_totals_reconcile_and_future_prices_are_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            holdings, imported = fixture(Path(directory))
            snapshot = build_snapshot(holdings, imported, "2026-01-15")
            prices = self.prices(holdings)
            future = prices.copy()
            future["date"], future["unit_price"] = "2026-02-01", 1000
            detail, summary = value_snapshots(snapshot, pd.concat([prices, future]))
            total = summary.loc[summary.category.eq("global"), "total_value"].iloc[0]
            self.assertEqual(total, 70)
            self.assertEqual(total, summary.loc[summary.category.ne("global"), "total_value"].sum())
            self.assertTrue(detail.price_age_days.eq(14).all())

    def test_unknown_empty_and_not_imported_are_distinct(self):
        holdings = pd.DataFrame([[identity("skin", "A"), "skin", "A", None]], columns=HOLDINGS)
        snapshot = build_snapshot(holdings, {"skin", "case"}, "2026-01-15")
        _, summary = value_snapshots(snapshot, self.prices(holdings))
        by = summary.set_index("category")
        self.assertEqual(by.loc["case", "total_value"], 0)
        self.assertTrue(pd.isna(by.loc["skin", "total_value"]))
        self.assertEqual(by.loc["skin", "unknown_quantities"], 1)
        self.assertEqual(by.loc["global", "categories_not_imported"], 4)
        self.assertTrue(pd.isna(by.loc["global", "total_value"]))

    def test_monthly_replacement_empty_transitions_and_atomic_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            holdings, imported = fixture(root)
            path = root / "global.csv"
            save_snapshot(holdings, imported, "2025-12-10", path)
            save_snapshot(holdings, imported, "2026-01-10", path)
            empty = holdings.iloc[:0]
            saved = save_snapshot(empty, imported, "2026-01-20", path)
            before = path.read_bytes()
            save_snapshot(empty, imported, "2026-01-20", path)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(saved.snapshot_date.nunique(), 2)
            _, totals = value_snapshots(saved, self.prices(holdings))
            self.assertEqual(totals.loc[totals.category.eq("global"), "total_value"].iloc[-1], 0)
            with patch("os.replace", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    save_snapshot(holdings, imported, "2026-02-01", path)
            self.assertEqual(path.read_bytes(), before)

    def test_corrupt_history_is_preserved_and_school_never_saves(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            fixture(root)
            with patch("global_snapshots.save_snapshot", side_effect=AssertionError("write")):
                report(root, "school", "2026-01-01")
            path = root / "data/processed/global_inventory_history.csv"
            path.write_text("broken\n1\n")
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                report(root, "home", "2026-01-01")
            self.assertEqual(before, path.read_bytes())


if __name__ == "__main__":
    unittest.main()
