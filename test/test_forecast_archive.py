"""Immutable, past-only forecast issuance and common-window scoring."""

from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from test_multicategory_prices import fixture
from test_global_analysis import market_fixture, run_notebook
from forecast_archive import digest, evaluate, issue, records, save_record


class ForecastArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.holdings, _ = fixture(self.root)
        self.prices = market_fixture(self.holdings, 4)
        self.path = self.root / "data/processed/market_observations.csv"
        self.prices.to_csv(self.path, index=False)
        self.directory = self.root / "data/processed/forecast_archive"

    def emit(self, **kwargs):
        return issue(self.root, clock=lambda: pd.Timestamp("2023-04-15 12:00"), **kwargs)

    def test_real_issues_store_frozen_baskets_versions_and_baselines(self):
        saved = self.emit()
        self.assertEqual(len(saved), 7)
        global_record = next(r for r in saved if r["category"] == "global")
        self.assertEqual(global_record["kind"], "issued")
        self.assertEqual(global_record["target_date"], "2023-04-30T00:00:00")
        self.assertEqual(global_record["predictions"], dict(persistence=300, trend=400, ridge=None))
        self.assertEqual(len(global_record["basket"]), 6)
        self.assertAlmostEqual(sum(b["weight"] for b in global_record["basket"]), 1)
        self.assertIn("scikit-learn", global_record["software"])
        self.assertIsNone(global_record["training_end"])
        self.assertEqual(len(global_record["data_hash"]), 64)

    def test_identical_retry_keeps_original_emission_and_archive_bytes(self):
        self.emit()
        before = {p: p.read_bytes() for p in self.directory.glob("*.json")}
        retried = issue(self.root, clock=lambda: pd.Timestamp("2023-04-16"))
        self.assertEqual(before, {p: p.read_bytes() for p in self.directory.glob("*.json")})
        self.assertEqual(retried[0]["emitted_at"], "2023-04-15T12:00:00")

    def test_changed_inputs_require_explicit_revision_without_overwriting(self):
        self.emit()
        before = {p: p.read_bytes() for p in self.directory.glob("*.json")}
        changed = self.prices.copy()
        changed.loc[changed.date.eq(pd.Timestamp("2023-03-31")), "unit_price"] = 25
        changed.to_csv(self.path, index=False)
        with self.assertRaisesRegex(ValueError, "revision"):
            self.emit()
        self.assertEqual(before, {p: p.read_bytes() for p in self.directory.glob("*.json")})
        self.emit(revision=2)
        self.assertEqual(len(records(self.directory)), 14)

    def test_future_data_does_not_change_issued_forecasts_or_fingerprint(self):
        initial = self.emit()
        self.prices.loc[self.prices.date.eq(pd.Timestamp("2023-04-30")), "unit_price"] = 10000
        self.prices.to_csv(self.path, index=False)
        self.assertEqual(initial, self.emit())

    def test_pending_until_close_then_compare_methods_on_same_dates(self):
        self.emit()
        pending, metrics = evaluate(self.directory, self.prices, "2023-04-30 18:00")
        self.assertTrue(pending.status.eq("pending").all())
        self.assertTrue(metrics.empty)
        completed, metrics = evaluate(self.directory, self.prices, "2023-05-01")
        self.assertTrue(completed.status.eq("evaluated").all())
        np.testing.assert_allclose(completed.actual, 400)
        self.assertEqual(set(metrics.method), {"persistence", "trend"})
        self.assertEqual(metrics.windows.nunique(), 1)
        np.testing.assert_allclose(metrics.loc[metrics.method.eq("trend"), "MAE"], 0, atol=1e-10)

    def test_zero_targets_have_finite_metrics_and_no_future_price_substitution(self):
        self.emit()
        prices = self.prices.copy()
        prices.loc[prices.date.eq(pd.Timestamp("2023-04-30")), "unit_price"] = 0
        future = prices.loc[prices.date.eq(pd.Timestamp("2023-04-30"))].copy()
        future["date"], future["unit_price"] = pd.Timestamp("2023-05-01"), 1000
        details, metrics = evaluate(self.directory, pd.concat([prices, future]), "2023-05-02")
        self.assertTrue(details.actual.eq(0).all())
        self.assertTrue(np.isfinite(metrics[["MAE", "RMSE"]]).all().all())

    def test_stale_missing_or_estimated_target_prices_are_unavailable(self):
        self.emit(max_age_days=10)
        missing = self.prices.loc[self.prices.date.lt("2023-04-01")]
        details, metrics = evaluate(self.directory, missing, "2023-05-01")
        self.assertTrue(details.status.eq("unavailable").all())
        self.assertTrue(metrics.empty)
        estimated = self.prices.copy()
        estimated.loc[estimated.date.eq(pd.Timestamp("2023-04-30")), "date_estimated"] = True
        details, _ = evaluate(self.directory, estimated, "2023-05-01")
        self.assertTrue(details.status.eq("unavailable").all())

    def test_retrospective_and_real_issues_are_separate_samples(self):
        self.emit()
        issue(self.root, retrospective_as_of="2023-04-15", clock=lambda: pd.Timestamp("2023-06-01"))
        details, metrics = evaluate(self.directory, self.prices, "2023-06-02")
        self.assertEqual(set(details.kind), {"issued", "retrospective"})
        self.assertEqual(set(metrics.kind), {"issued", "retrospective"})
        with self.assertRaises(ValueError):
            self.emit(retrospective_as_of="2030-01-01")

    def test_basket_change_needs_revision_and_uses_original_basket_for_actual(self):
        initial = self.emit()
        global_record = next(r for r in initial if r["category"] == "global")
        for file in (self.root / "data/processed").glob("*_inventory.csv"):
            frame = pd.read_csv(file)
            frame.iloc[0:0].to_csv(file, index=False)
        details, _ = evaluate(self.directory, self.prices, "2023-05-01")
        global_result = details.loc[details.category.eq("global")].iloc[0]
        self.assertAlmostEqual(global_result.actual, 400)
        self.assertEqual(global_result.basket_hash, digest(dict(base_date=global_record["base_date"], basket=global_record["basket"])))

    def test_archives_are_unchanged_by_evaluation_and_corruption_is_rejected(self):
        self.emit()
        before = {p: p.read_bytes() for p in self.directory.glob("*.json")}
        evaluate(self.directory, self.prices, "2023-05-01")
        self.assertEqual(before, {p: p.read_bytes() for p in self.directory.glob("*.json")})
        record = records(self.directory)[0]
        record["predictions"]["trend"] = 1
        with self.assertRaisesRegex(ValueError, "integrity"):
            save_record(record, self.directory)

    def test_empty_archive_history_and_target_period_filter(self):
        details, metrics = evaluate(self.directory, self.prices, "2023-05-01")
        self.assertTrue(details.empty)
        self.assertTrue(metrics.empty)
        self.prices.iloc[:0].to_csv(self.path, index=False)
        self.assertEqual(self.emit(), [])
        self.assertFalse(self.directory.exists())
        self.prices.to_csv(self.path, index=False)
        self.emit()
        details, metrics = evaluate(self.directory, self.prices, "2023-05-01", target_start="2023-05-31")
        self.assertTrue(details.empty)
        self.assertTrue(metrics.empty)

    def test_model_saved_when_available_and_compared_on_common_windows(self):
        prices = market_fixture(self.holdings, 18)
        prices.to_csv(self.path, index=False)
        issue(self.root, min_train=3, clock=lambda: pd.Timestamp("2024-06-15"))
        details, metrics = evaluate(self.directory, prices, "2024-07-01")
        self.assertTrue(details.ridge.notna().all())
        model = metrics.loc[metrics["sample"].eq("model_common")]
        self.assertEqual(set(model.method), {"persistence", "trend", "ridge"})
        self.assertTrue(model.windows.eq(1).all())

    def test_common_samples_do_not_mix_model_and_baseline_windows(self):
        prices = market_fixture(self.holdings, 18)
        prices.to_csv(self.path, index=False)
        issue(self.root, clock=lambda: pd.Timestamp("2024-03-15"))
        issue(self.root, clock=lambda: pd.Timestamp("2024-04-15"))
        details, metrics = evaluate(self.directory, prices, "2024-07-01")
        baseline = metrics.loc[metrics["sample"].eq("baseline_common")]
        model = metrics.loc[metrics["sample"].eq("model_common")]
        self.assertTrue(baseline.windows.eq(2).all())
        self.assertTrue(model.windows.eq(1).all())
        self.assertEqual(set(model.method), {"persistence", "trend", "ridge"})
        _, filtered = evaluate(self.directory, prices, "2024-07-01", target_start="2024-04-01", target_end="2024-04-30")
        self.assertTrue(filtered.windows.eq(1).all())

    def test_revised_baskets_are_scored_separately(self):
        self.emit()
        path = self.root / "data/processed/skins_inventory.csv"
        pd.read_csv(path).iloc[0:0].to_csv(path, index=False)
        with self.assertRaises(ValueError):
            self.emit()
        self.emit(revision=2)
        details, metrics = evaluate(self.directory, self.prices, "2023-05-01")
        self.assertEqual(details.loc[details.category.eq("global"), "basket_hash"].nunique(), 2)
        self.assertTrue(metrics.windows.eq(1).all())

    def test_evaluation_before_emission_never_scores_a_future_issue(self):
        self.emit()
        details, metrics = evaluate(self.directory, self.prices, "2023-04-01")
        self.assertTrue(details.status.eq("pending").all())
        self.assertTrue(details.reason.eq("not_emitted_at_evaluation_cutoff").all())
        self.assertTrue(metrics.empty)

    def test_notebook_reads_existing_archives_without_changing_them(self):
        self.emit()
        before = {p: p.read_bytes() for p in self.directory.glob("*.json")}
        scope, _ = run_notebook("prediction_book.ipynb", self.root)
        self.assertIn("archive_details", scope)
        self.assertEqual(len(scope["archive_details"]), 7)
        self.assertEqual(before, {p: p.read_bytes() for p in self.directory.glob("*.json")})


if __name__ == "__main__":
    unittest.main()
