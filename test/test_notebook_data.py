"""Cross-entry-point parity, including actual notebook execution and owner import."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from test_global_analysis import market_fixture, run_notebook
from test_multicategory_prices import fixture
from test_steam_inventory_import import catalog_fixture, export_fixture, owner_export_fixture
from test_steam_inventory_coverage import legacy_portfolio
from dashboard import view
from global_snapshots import save_snapshot
from notebook_data import category_report, notebook_context
from portfolio_data import CATEGORIES, PRICES, identity, load_holdings
from steam_inventory import apply, preview


def files(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


class NotebookDataTests(unittest.TestCase):
    def assert_parity(self, root, category, *, now='2026-11-03', historical=False):
        end = '2026-10-31' if historical else None
        cutoff = '2026-10-31 23:59:59.999999999' if historical else now
        report = category_report(root, categories=[category], as_of=cutoff, historical=historical)
        dashboard = view(root, category=category, now=now, end=end, components='overview')
        pd.testing.assert_frame_equal(report['detail'], dashboard['detail'])
        pd.testing.assert_frame_equal(report['summary'], dashboard['current'])
        self.assertEqual(report['provenance']['basis'], dashboard['provenance']['basis'])
        return report

    def test_complete_partial_empty_and_future_prices_have_identical_values(self):
        for mode in ('complete', 'partial', 'empty'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                if mode != 'empty':
                    holdings, _ = fixture(root)
                    holdings.loc[0, 'quantity'] = None
                    if mode == 'partial':
                        holdings.loc[holdings.category.eq('case'), ['item_name', 'quantity']].rename(columns={'item_name': 'case_name'}).to_csv(root / 'data/processed/drop_cases_inventory.csv', index=False)
                        (root / 'data/processed/souvenirs_inventory.csv').unlink()
                    prices = market_fixture(holdings)
                    prices = pd.concat([prices, prices.assign(date='2027-01-01', unit_price=99999)], ignore_index=True)
                    if mode == 'partial':
                        prices = prices.loc[~prices.category.eq('skin')]
                    prices.to_csv(root / 'data/processed/market_observations.csv', index=False)
                before = files(root)
                with patch('socket.socket', side_effect=AssertionError('network forbidden')):
                    for category in CATEGORIES:
                        report = self.assert_parity(root, category)
                        self.assertFalse(report['prices'].date.gt(pd.Timestamp('2026-11-03')).any())
                self.assertEqual(before, files(root))

    def test_owner_replacement_and_visible_observations_are_shared_but_not_added(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy_portfolio(root)
            item = dict(item_id=identity('case', 'Example'), category='case', item_name='Example')
            pd.DataFrame([dict(item, date='2026-11-01', unit_price=4, source='steam', currency='EUR', date_estimated=False)], columns=PRICES).to_csv(root / 'data/processed/market_observations.csv', index=False)
            owner = owner_export_fixture()
            plan = preview(owner, catalog_fixture(), root)
            apply(owner, catalog_fixture(), plan['review_token'], root, 'home')
            visible = export_fixture()
            visible['pages'][0]['assets'][0]['amount'] = '99'
            plan = preview(visible, catalog_fixture(), root)
            apply(visible, catalog_fixture(), plan['review_token'], root, 'home')
            before = files(root)
            report = self.assert_parity(root, 'case')
            self.assertEqual(report['holdings'].quantity.tolist(), [2])
            self.assertEqual(report['holdings'].market_value.tolist(), [8])
            self.assertEqual(report['provenance']['basis'], 'owner_declared_full_portfolio')
            self.assertEqual(report['provenance']['collected_at'], '2026-11-01')
            with patch.dict(os.environ, {'CKIN2_AS_OF': '2026-11-03'}):
                scope, _ = run_notebook('cases_book.ipynb', root)
                self.assertEqual(scope['current_value'].quantity.tolist(), [2])
                self.assertEqual(scope['known_value'], 8)
            self.assertEqual(before, files(root))
            path = root / 'data/processed/steam_inventory_override.json'
            value = json.loads(path.read_text())
            value.pop('inventory_scope')
            path.write_text(json.dumps(value))
            self.assertEqual(self.assert_parity(root, 'case')['provenance']['basis'], 'legacy_override_coverage_unverified')

    def test_historical_selection_uses_snapshot_quantities_and_never_future_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            holdings, imported = fixture(root)
            path = root / 'data/processed/global_inventory_history.csv'
            save_snapshot(holdings.assign(quantity=3), imported, '2026-10-01', path)
            save_snapshot(holdings.assign(quantity=1000), imported, '2026-12-01', path)
            prices = market_fixture(holdings).assign(date='2026-10-01', unit_price=4)
            prices.to_csv(root / 'data/processed/market_observations.csv', index=False)
            before = files(root)
            for category in CATEGORIES:
                report = self.assert_parity(root, category, historical=True)
                self.assertEqual(report['holdings'].quantity.tolist(), [3])
                self.assertEqual(report['holdings'].market_value.tolist(), [12])
            self.assertEqual(before, files(root))
        with tempfile.TemporaryDirectory() as temporary:
            self.assertTrue(self.assert_parity(Path(temporary), 'case', historical=True)['holdings'].empty)

    def test_every_category_notebook_executes_on_complete_partial_and_empty_fixtures(self):
        for mode in ('complete', 'partial', 'empty'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                if mode != 'empty':
                    holdings, _ = fixture(root)
                    if mode == 'partial':
                        (root / 'data/processed/skins_inventory.csv').unlink()
                        path = root / 'data/processed/drop_cases_inventory.csv'
                        pd.DataFrame({'case_name': ['Recoil'], 'quantity': [None]}).to_csv(path, index=False)
                    prices = market_fixture(holdings)
                    if mode == 'partial':
                        prices = prices.loc[prices.category.eq('case')]
                    prices.to_csv(root / 'data/processed/market_observations.csv', index=False)
                before = files(root)
                with patch.dict(os.environ, {'CKIN2_AS_OF': '2023-04-01'}), patch('socket.socket', side_effect=AssertionError('network forbidden')):
                    for name, category in [('cases', 'case'), ('skins', 'skin'), ('souvenirs', 'souvenir'), ('others', 'sticker')]:
                        scope, _ = run_notebook(name + '_book.ipynb', root)
                        report = scope.get('notebook_result', scope.get('result'))
                        expected = view(root, category=category, now='2023-04-01', components='overview')
                        actual = report['summary'].loc[report['summary'].category.eq(category)].reset_index(drop=True)
                        wanted = expected['current'].loc[expected['current'].category.eq(category)].reset_index(drop=True)
                        pd.testing.assert_frame_equal(actual, wanted)
                self.assertEqual(before, files(root))

    def test_exact_variants_acquisition_separation_and_declared_costs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / 'data/processed'
            directory.mkdir(parents=True)
            names = ['AK-47 | Test (Factory New)', 'StatTrak™ AK-47 | Test (Factory New)', 'AK-47 | Test (Field-Tested)']
            pd.DataFrame(dict(item_name=names, quantity=[2, 3, 4], purchase_unit_price=[1, 2, None], purchase_date=[None]*3)).to_csv(directory / 'skins_inventory.csv', index=False)
            pd.DataFrame(dict(item_name=names * 2, date=['2026-01-01']*3 + ['2026-01-02']*3,
                              unit_price=[999]*3 + [10, 20, 0], source_column=[0]*3 + [2]*3,
                              date_estimated=[False]*6)).to_csv(directory / 'skins_prices.csv', index=False)
            before = files(root)
            report = self.assert_parity(root, 'skin')
            self.assertEqual(report['holdings'].item_id.nunique(), 3)
            self.assertEqual(report['holdings'].market_value.tolist(), [20, 60, 0])
            self.assertEqual(report['holdings'].purchase_cost.iloc[:2].tolist(), [2, 6])
            self.assertTrue(pd.isna(report['holdings'].purchase_cost.iloc[2]))
            self.assertEqual(report['acquisitions'].unit_price.tolist(), [999]*3)
            self.assertEqual(report['prices'].set_index('item_name').unit_price.to_dict(), dict(zip(names, [10, 20, 0])))
            self.assertEqual(before, files(root))

    def test_context_rejects_ambiguous_dates_and_keeps_explicit_root(self):
        with patch.dict(os.environ, {'CKIN2_DATA_ROOT': '/tmp/ckin2-synthetic', 'CKIN2_AS_OF': '2026-01-01'}):
            root, stamp = notebook_context()
            self.assertEqual(root, Path('/tmp/ckin2-synthetic'))
            self.assertEqual(stamp, pd.Timestamp('2026-01-01'))
        for stamp in ('invalid', '2026-01-01T00:00:00Z'):
            with patch.dict(os.environ, {'CKIN2_AS_OF': stamp}), self.assertRaises(ValueError):
                notebook_context()
