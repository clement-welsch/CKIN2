"""Parity of authored notebooks and dashboard on local synthetic portfolios."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from test_global_analysis import market_fixture, run_notebook
from test_multicategory_prices import fixture
from dashboard import view
from global_snapshots import save_snapshot
from notebook_portfolio import portfolio_report
from portfolio_data import CATEGORIES


class NotebookPortfolioTests(unittest.TestCase):
    def test_complete_partial_empty_and_owner_replacement_match_dashboard(self):
        for scenario in ('complete', 'partial', 'empty', 'owner', 'unknown'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                if scenario != 'empty':
                    holdings, imported = fixture(root)
                    target = root / 'data/processed'
                    market_fixture(holdings).to_csv(target / 'market_observations.csv', index=False)
                    save_snapshot(holdings, imported, '2023-01-31', target / 'global_inventory_history.csv')
                    # Visible quantities must never become portfolio quantities.
                    (target / 'steam_inventory_observation.json').write_text(json.dumps({'holdings': holdings.assign(quantity=999).to_dict('records')}))
                    if scenario == 'partial':
                        (target / 'skins_inventory.csv').unlink()
                    if scenario == 'unknown':
                        (target / 'drop_cases_inventory.csv').write_text('case_name,quantity\nRecoil,\n')
                    if scenario == 'owner':
                        (target / 'steam_inventory_override.json').write_text(json.dumps({
                            'schema': 1, 'inventory_scope': 'full_portfolio',
                            'imported': list(CATEGORIES),
                            'holdings': holdings.assign(quantity=8).to_dict('records')}))
                before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
                with patch.dict('os.environ', {'CKIN2_AS_OF': '2023-04-01'}):
                    for name, category in [('cases', 'case'), ('skins', 'skin'), ('souvenirs', 'souvenir'), ('others', 'all'), ('global', 'all'), ('prediction', 'all')]:
                        scope, _ = run_notebook(name + '_book.ipynb', root)
                        result = scope['result'] if name == 'global' else scope['report']
                        expected = view(root, category=category, now='2023-04-01', components='forecasts' if name == 'prediction' else 'overview')
                        for key in ('current', 'detail', 'historical'):
                            pd.testing.assert_frame_equal(result[key], expected[key])
                self.assertEqual(before, {p: p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_acquisition_references_do_not_value_the_portfolio(self):
        from notebook_portfolio import category_reports
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            holdings, _ = fixture(root)
            target = root / 'data/processed'
            name = holdings.loc[holdings.category.eq('skin'), 'item_name'].iloc[0]
            pd.DataFrame([dict(date='2023-01-01', item_name=name, unit_price=999,
                               source_column=0)]).to_csv(target / 'skins_prices.csv', index=False)
            result = portfolio_report(root, category='skin', now='2023-04-01')
            skin = category_reports(root, result)[0]
            self.assertEqual(len(skin['acquisitions']), 1)
            self.assertTrue(skin['prices'].empty)
            self.assertTrue(result['current'].total_value.isna().all())

    def test_past_selection_uses_historical_quantities_and_excludes_future_prices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            holdings, imported = fixture(root)
            target = root / 'data/processed'
            market_fixture(holdings).to_csv(target / 'market_observations.csv', index=False)
            save_snapshot(holdings.assign(quantity=3), imported, '2023-01-31', target / 'global_inventory_history.csv')
            options = dict(category='skin', item_id=holdings.loc[holdings.category.eq('skin'), 'item_id'].iloc[0], start='2023-01-01', end='2023-02-01', now='2023-04-01')
            result = portfolio_report(root, **options)
            expected = view(root, components='overview', **options)
            pd.testing.assert_frame_equal(result['detail'], expected['detail'])
            self.assertEqual(result['detail'].loc[result['detail'].state.eq('holdings'), 'quantity'].tolist(), [3])
            self.assertTrue(result['prices'].date.le(result['cutoff']).all())
            self.assertIn('historiques', result['context'].quantity_source.iloc[0])
