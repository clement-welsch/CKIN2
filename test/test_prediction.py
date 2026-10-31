from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from test_multicategory_prices import fixture
from test_global_analysis import market_fixture, run_notebook
from global_analysis import market_indices
from prediction import evaluate_series, experiment, monthly_series, scores


class PredictionTests(unittest.TestCase):
    def series(self, count=36):
        return pd.DataFrame({"date": pd.date_range("2020-01-31", periods=count, freq="ME"),
                             "category": "global", "index_100": 100+np.arange(count)*2.0})

    def test_walk_forward_never_uses_future_targets_or_future_scaling(self):
        original = self.series()
        before, future, audit = evaluate_series(original)
        changed = original.copy()
        cutoff = original.date.iloc[20]
        changed.loc[changed.date.gt(cutoff), "index_100"] = 10000
        after, _, _ = evaluate_series(changed)
        columns = ["origin", "persistence", "trend", "ridge", "training_end", "training_pairs"]
        pd.testing.assert_frame_equal(before.loc[before.origin.le(cutoff), columns].reset_index(drop=True),
                                      after.loc[after.origin.le(cutoff), columns].reset_index(drop=True))
        self.assertTrue(before.training_end.dropna().le(before.loc[before.training_end.notna(), "origin"]).all())
        self.assertTrue(before.target_date.gt(before.origin).all())
        metrics = scores(before)
        model = metrics.loc[metrics["sample"].eq("model_common")]
        self.assertEqual(model.windows.nunique(), 1)
        self.assertEqual(set(model.method), {"persistence", "trend", "ridge"})
        self.assertGreater(audit.model_windows.iloc[0], 0)
        self.assertEqual(future.target_date.iloc[0], pd.Timestamp("2023-01-31"))

    def test_gaps_are_not_bridged_and_zero_targets_have_finite_metrics(self):
        series = self.series(8)
        series.loc[2:4, "index_100"] = np.nan
        series.loc[5:, "index_100"] = 0
        backtests, _, audit = evaluate_series(series)
        self.assertTrue(backtests.ridge.isna().all())
        self.assertEqual(audit.missing_months.iloc[0], 3)
        metrics = scores(backtests)
        self.assertTrue(np.isfinite(metrics[["MAE", "RMSE"]].to_numpy()).all())
        self.assertFalse(backtests.origin.isin(series.loc[2:5, "date"]).any())

    def test_insufficient_history_has_baselines_but_no_model(self):
        backtests, future, audit = evaluate_series(self.series(3))
        self.assertEqual(len(backtests), 1)
        self.assertEqual(audit.status.iloc[0], "insufficient_model_history")
        self.assertTrue(future.ridge.isna().all())

    def test_month_end_sampling_uses_no_future_or_estimated_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            holdings, _ = fixture(Path(directory))
            prices = market_fixture(holdings, 5)
            prices.loc[prices.date.eq("2023-02-28"), "date_estimated"] = True
            result = experiment(holdings, prices, "2023-04-15", max_age_days=10)
            monthly = result["monthly"]
            self.assertTrue(monthly.date.le("2023-03-31").all())
            self.assertTrue(monthly.loc[monthly.date.eq("2023-02-28"), "index_100"].isna().all())
            past = experiment(holdings, prices.loc[prices.date.le("2023-04-15")], "2023-04-15", max_age_days=10)
            pd.testing.assert_frame_equal(result["monthly"], past["monthly"])

    def test_full_prediction_notebook_long_short_and_empty(self):
        for months in [36, 3, 0]:
            with self.subTest(months=months), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                if months:
                    holdings, _ = fixture(root)
                    market_fixture(holdings, months).to_csv(root / "data/processed/market_observations.csv", index=False)
                scope, figures = run_notebook("prediction_book.ipynb", root)
                if months == 36:
                    self.assertEqual(len(figures), 3)
                    self.assertTrue(scope["prediction"]["audit"].model_windows.gt(0).all())
                elif months == 3:
                    self.assertTrue(scope["prediction"]["audit"].model_windows.eq(0).all())
                else:
                    self.assertEqual(figures, [])
                    self.assertEqual(len(scope["prediction"]["audit"]), 7)


if __name__ == "__main__":
    unittest.main()
