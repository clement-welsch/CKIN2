from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from dashboard import render, view
from global_analysis import explain_changes
from global_snapshots import build_snapshot
from test_global_analysis import market_fixture
from test_multicategory_prices import fixture


class DashboardPerformanceTests(unittest.TestCase):
    def test_filtered_changes_keep_previous_snapshot_and_match_shared_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            holdings, imported = fixture(root)
            prices = market_fixture(holdings)
            prices.to_csv(root / 'data/processed/market_observations.csv', index=False)
            later = holdings.copy()
            later.loc[0, 'quantity'] += 2
            history = pd.concat([build_snapshot(holdings, imported, '2023-01-31'),
                                 build_snapshot(later, imported, '2023-02-28')])
            history.to_csv(root / 'data/processed/global_inventory_history.csv', index=False)
            before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            item = holdings.iloc[0]
            result = view(root, category=item.category, item_id=item.item_id,
                          start='2023-02-01', end='2023-02-28', now='2023-04-01', components='performance')
            expected = explain_changes(history, prices)
            expected = expected.loc[expected.item_id.eq(item.item_id)].reset_index(drop=True)
            pd.testing.assert_frame_equal(result['contributions'].reset_index(drop=True), expected)
            self.assertEqual(result['contributions'].start_date.iloc[0], pd.Timestamp('2023-01-31'))
            html = render(root, {'page': 'performance', 'category': item.category,
                                 'item_id': item.item_id, 'start': '2023-02-01', 'end': '2023-02-28'}, now='2023-04-01')
            self.assertIn('Décomposition des variations', html)
            self.assertIn('Ventes réalisées et frais', html)
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_empty_performance_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            html = render(Path(directory), {'page': 'performance'}, now='2023-04-01')
            self.assertIn('Deux snapshots', html)
            self.assertIn('inventaire initial absent', html)
