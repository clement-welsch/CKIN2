from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from dashboard import render, view
from forecast_archive import evaluate, issue, load_archive_prices
from prediction import experiment, scores
from test_global_analysis import market_fixture
from test_multicategory_prices import fixture


class DashboardForecastTests(unittest.TestCase):
    def test_period_filters_targets_after_training_and_preserves_archive_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            holdings, _ = fixture(root)
            prices = market_fixture(holdings, 18)
            path = root / 'data/processed/market_observations.csv'
            prices.to_csv(path, index=False)
            issue(root, clock=lambda: pd.Timestamp('2024-04-15'))
            before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            result = view(root, category='case', start='2024-03-01', now='2024-07-01', components='forecasts')
            expected = experiment(holdings.loc[holdings.category.eq('case')], prices, '2024-07-01')
            expected = expected['backtests'].loc[lambda f: f.category.eq('case') & f.target_date.ge('2024-03-01')]
            pd.testing.assert_frame_equal(result['prediction']['backtests'], expected)
            pd.testing.assert_frame_equal(result['prediction']['scores'], scores(expected))
            self.assertTrue(result['prediction']['backtests'].training_end.lt(result['prediction']['backtests'].target_date).all())
            _, metrics = evaluate(root / 'data/processed/forecast_archive', load_archive_prices(root), '2024-07-01',
                                  target_start=pd.Timestamp('2024-03-01'), target_end=pd.Timestamp('2024-07-01'))
            pd.testing.assert_frame_equal(result['archive_metrics'], metrics.loc[metrics.category.eq('case')])
            html = render(root, {'page': 'forecasts', 'category': 'case', 'start': '2024-03-01'}, now='2024-07-01')
            self.assertIn('Validation chronologique', html)
            self.assertIn('MAE hors', html)
            self.assertIn('training_end', html)
            item = holdings.loc[holdings.category.eq('case'), 'item_id'].iloc[0]
            filtered = view(root, category='case', item_id=item, now='2024-07-01', components='forecasts')
            self.assertTrue(filtered['archive'].empty)
            self.assertTrue(filtered['archive_metrics'].empty)
            past = view(root, end='2024-04-10', now='2024-07-01', components='forecasts')
            self.assertTrue(past['archive'].empty)
            self.assertTrue(past['archive_metrics'].empty)
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_empty_history_and_zero_targets_are_supported_without_future_leak(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIn('historique insuffisant', render(root, {'page': 'forecasts'}, now='2024-07-01'))
            holdings, _ = fixture(root)
            prices = market_fixture(holdings, 5)
            prices.loc[prices.date.eq(prices.date.max()), 'unit_price'] = 0
            path = root / 'data/processed/market_observations.csv'
            prices.to_csv(path, index=False)
            original = view(root, now='2023-06-01', components='forecasts')['prediction']
            self.assertTrue(original['backtests'].actual.eq(0).any())
            future = prices.copy()
            future['date'] = pd.Timestamp('2030-01-01')
            future['unit_price'] = 99999
            pd.concat([prices, future]).to_csv(path, index=False)
            changed = view(root, now='2023-06-01', components='forecasts')['prediction']
            for key in ('backtests', 'scores', 'future'):
                pd.testing.assert_frame_equal(original[key], changed[key])
