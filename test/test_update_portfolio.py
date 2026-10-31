"""End-to-end update workflow using temporary CSVs and simulated Steam."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from test_multicategory_prices import fixture
from update_portfolio import run, SUCCESS, PARTIAL, FAILURE


class UpdatePortfolioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        fixture(self.root)
        self.output = StringIO()

    def update(self, **kwargs):
        with redirect_stdout(self.output):
            return run(self.root, pause=lambda _: None, **kwargs)

    def contents(self):
        return {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*.csv")}

    def test_complete_workflow_and_retry_do_not_duplicate_rows(self):
        self.assertEqual(self.update(environment="home", when="2026-10-31 12:00", fetch=lambda _: 2), SUCCESS)
        before = self.contents()
        self.assertEqual(self.update(environment="home", when="2026-10-31 12:00", fetch=lambda _: 2), SUCCESS)
        self.assertEqual(before, self.contents())
        self.assertIn("snapshot: saved", self.output.getvalue())
        self.assertIn("Monthly snapshot history", self.output.getvalue())

    def test_partial_collection_preserves_old_prices_and_reports_failure(self):
        self.update(environment="home", when="2026-10-01", fetch=lambda _: 2)
        fetch = Mock(side_effect=[3, None, None, None, None, None])
        self.assertEqual(self.update(environment="home", when="2026-10-31", fetch=fetch), PARTIAL)
        prices = pd.read_csv(self.root / "data/processed/market_observations.csv")
        self.assertEqual(len(prices), 7)
        self.assertIn("5 failed", self.output.getvalue())
        self.assertIn("price_age_days", self.output.getvalue())

    def test_school_never_contacts_steam_or_writes_data(self):
        before = self.contents()
        fetch = Mock(side_effect=AssertionError("network"))
        self.assertEqual(self.update(environment="school", when="2026-10-31", fetch=fetch), PARTIAL)
        fetch.assert_not_called()
        self.assertEqual(before, self.contents())
        self.assertFalse((self.root / "data/processed/global_inventory_history.csv").exists())

    def test_invalid_inputs_fail_before_network_or_writes(self):
        for target in ("market_catalog.csv", "drop_cases_inventory.csv", "global_inventory_history.csv"):
            with self.subTest(target=target):
                path = self.root / "data/processed" / target
                original = path.read_bytes() if path.exists() else None
                path.write_text("invalid\nrow\n", encoding="utf-8")
                before = self.contents()
                fetch = Mock(side_effect=AssertionError("network"))
                self.assertEqual(self.update(environment="home", when="2026-10-31", fetch=fetch), FAILURE)
                fetch.assert_not_called()
                self.assertEqual(before, self.contents())
                if original is None:
                    path.unlink()
                else:
                    path.write_bytes(original)

    def test_snapshot_failure_preserves_collection_and_retry_recovers(self):
        with patch("global_snapshots.atomic_csv", side_effect=OSError("disk full")):
            self.assertEqual(self.update(environment="home", when="2026-10-31", fetch=lambda _: 2), FAILURE)
        self.assertIn("snapshot: FAILED", self.output.getvalue())
        prices = self.root / "data/processed/market_observations.csv"
        before = prices.read_bytes()
        self.assertEqual(self.update(environment="home", when="2026-10-31", fetch=lambda _: 2), SUCCESS)
        self.assertEqual(before, prices.read_bytes())

    def test_school_reuses_existing_snapshot_without_modification(self):
        self.update(environment="home", when="2026-10-01", fetch=lambda _: 2)
        before = self.contents()
        fetch = Mock(side_effect=AssertionError("network"))
        self.assertEqual(self.update(environment="school", when="2026-10-31", fetch=fetch), SUCCESS)
        self.assertEqual(before, self.contents())
        fetch.assert_not_called()

    def test_report_failure_keeps_both_successful_writes(self):
        with patch("update_portfolio.analyze", side_effect=ValueError("report unavailable")):
            self.assertEqual(self.update(environment="home", when="2026-10-31", fetch=lambda _: 2), FAILURE)
        self.assertIn("report: FAILED", self.output.getvalue())
        self.assertTrue((self.root / "data/processed/market_observations.csv").exists())
        self.assertTrue((self.root / "data/processed/global_inventory_history.csv").exists())

    def test_invalid_timestamp_fails_before_collection(self):
        before = self.contents()
        fetch = Mock(side_effect=AssertionError("network"))
        for when in ("invalid", "2026-10-31T12:00:00Z"):
            self.assertEqual(self.update(environment="home", when=when, fetch=fetch), FAILURE)
        fetch.assert_not_called()
        self.assertEqual(before, self.contents())


if __name__ == "__main__":
    unittest.main()
