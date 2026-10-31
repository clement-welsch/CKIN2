import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from test_multicategory_prices import fixture
from update_portfolio import FAILURE, PARTIAL, SUCCESS, main, run


class WorkflowTests(unittest.TestCase):
    def execute(self, root, mode="home", **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return run(root, mode, clock=lambda: pd.Timestamp("2026-10-31T12:00:00"),
                       pause=lambda _: None, **kwargs)

    def test_complete_workflow_timestamps_and_repeat_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            result = self.execute(root, fetch=lambda _: 5)
            self.assertEqual(result["code"], SUCCESS)
            self.assertEqual([s["stage"] for s in result["stages"]], ["validation", "collection", "snapshot", "report"])
            self.assertEqual(result["current"].loc[lambda f: f.category.eq("global"), "total_value"].iloc[0], 35)
            before = {p: p.read_bytes() for p in root.rglob("*.csv")}
            self.execute(root, fetch=lambda _: 5)
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*.csv")})

    def test_partial_collection_retains_previous_prices_and_marks_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            self.execute(root, fetch=lambda _: 4)
            result = self.execute(root, fetch=lambda n: None if n == "Recoil Case" else 5)
            self.assertEqual(result["code"], PARTIAL)
            self.assertEqual(result["collection"].outcome.eq("failed").sum(), 1)
            case = result["collection"].loc[lambda f: f.category.eq("case")].iloc[0]
            self.assertEqual(case.unit_price, 4)
            self.assertEqual(result["current"].loc[lambda f: f.category.eq("global"), "total_value"].iloc[0], 33)

    def test_missing_price_leaves_total_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            result = self.execute(root, fetch=lambda n: None if n == "Recoil Case" else 5)
            self.assertEqual(result["code"], PARTIAL)
            self.assertTrue(pd.isna(result["current"].loc[lambda f: f.category.eq("global"), "total_value"].iloc[0]))

    def test_preflight_failures_do_not_call_network_or_write(self):
        for kind in ["catalog", "history", "inventory", "date", "target"]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fixture(root)
                target = root / "data/processed"
                if kind == "catalog":
                    (target / "market_catalog.csv").write_text("broken\n1\n")
                elif kind == "history":
                    (target / "global_inventory_history.csv").write_text("broken\n1\n")
                elif kind == "inventory":
                    pd.DataFrame({"case_name": ["Recoil"], "quantity": [-1]}).to_csv(target / "drop_cases_inventory.csv", index=False)
                before = {p: p.read_bytes() for p in root.rglob("*.csv")}
                options = {"date": "2020-01-01"} if kind == "date" else {"snapshot_path": target / "market_catalog.csv"} if kind == "target" else {}
                with patch("update_market_prices.fetch_market_price", side_effect=AssertionError("Network reached")):
                    result = self.execute(root, **options)
                self.assertEqual(result["code"], FAILURE)
                self.assertEqual(result["stages"][-1]["stage"], "validation")
                self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*.csv")})

    def test_snapshot_failure_preserves_prices_and_retry_finishes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            with patch("update_portfolio.save_snapshot", side_effect=OSError("Disk unavailable")):
                result = self.execute(root, fetch=lambda _: 5)
            self.assertEqual(result["code"], FAILURE)
            self.assertEqual(result["stages"][-1]["stage"], "snapshot")
            prices = root / "data/processed/market_observations.csv"
            before = prices.read_bytes()
            result = self.execute(root, fetch=lambda _: 5)
            self.assertEqual(result["code"], SUCCESS)
            self.assertEqual(prices.read_bytes(), before)

    def test_school_and_cli_paths_are_read_only_and_respect_cutoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            self.execute(root, fetch=lambda _: 5)
            before = {p: p.read_bytes() for p in root.rglob("*.csv")}
            with patch("update_market_prices.fetch_market_price", side_effect=AssertionError("Network")), patch("update_portfolio.save_snapshot", side_effect=AssertionError("Write")):
                result = self.execute(root, "school", date="2026-01-01")
                self.assertEqual(result["code"], PARTIAL)
                self.assertTrue(result["historical"].empty)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["school", "--root", str(root), "--date", "2026-01-01",
                                           "--snapshot-path", str(root / "custom-history.csv")]), PARTIAL)
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*.csv")})

    def test_real_observation_times_precede_snapshot(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            fixture(root)
            moments = iter(pd.date_range("2026-10-31T12:00:00", periods=9, freq="s"))
            result = run(root, "home", clock=lambda: next(moments), fetch=lambda _: 5, pause=lambda _: None)
            prices = pd.read_csv(root / "data/processed/market_observations.csv")
            stamp = result["stages"][2]["timestamp"]
            self.assertEqual(result["code"], SUCCESS)
            self.assertEqual(prices.date.nunique(), 6)
            self.assertTrue(pd.to_datetime(prices.date).le(stamp).all())


if __name__ == "__main__":
    unittest.main()
