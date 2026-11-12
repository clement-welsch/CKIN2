from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from dashboard import render, view
from dashboard_status import coverage
from dashboard_overview import quantity_decrease_alert
from global_analysis import analyze
from global_snapshots import save_snapshot
from test_multicategory_prices import fixture
from test_global_analysis import market_fixture


class OverviewTests(unittest.TestCase):
    def test_quantity_decrease_alert_preserves_unknown_and_monthly_reference(self):
        from global_snapshots import build_snapshot
        from portfolio_data import HOLDINGS, identity
        old = pd.DataFrame([[identity('case', name), 'case', name, quantity]
                            for name, quantity in [('Recoil', 19), ('Unknown', 4), ('Opened', 1)]], columns=HOLDINGS)
        new = old.copy()
        new['quantity'] = [18, None, 0]
        history = pd.concat([build_snapshot(old, {'case'}, '2026-10-31'),
                             build_snapshot(new, {'case'}, '2026-11-12')])
        data = dict(snapshots=history, detail=build_snapshot(new, {'case'}, '2026-11-12'),
                    historical_mode=False, cutoff=pd.Timestamp('2026-11-12'))
        alert = quantity_decrease_alert(data)
        self.assertIn('Recoil : 19 → 18', alert)
        self.assertIn('Opened : 1 → 0', alert)
        self.assertNotIn('Unknown', alert)
        self.assertIn('2026-10-31', alert)
        self.assertIn('ne bloque pas', alert)
        data['detail'] = build_snapshot(old, {'case'}, '2026-11-12')
        self.assertEqual(quantity_decrease_alert(data), '')

    def test_complete_partial_empty_and_stale_use_shared_values_without_writes(self):
        for scenario in ('complete', 'partial', 'empty', 'stale'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                now = '2023-04-01'
                if scenario != 'empty':
                    holdings, _ = fixture(root)
                    prices = market_fixture(holdings)
                    if scenario == 'partial':
                        prices = prices.loc[prices.category.ne('skin')]
                        pd.DataFrame(dict(case_name=['Recoil'], quantity=[None])).to_csv(root / 'data/processed/drop_cases_inventory.csv', index=False)
                        (root / 'data/processed/souvenirs_inventory.csv').unlink()
                    prices.to_csv(root / 'data/processed/market_observations.csv', index=False)
                    if scenario == 'stale':
                        now = '2023-09-01'
                before = {p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
                with patch('socket.socket', side_effect=AssertionError('network')):
                    result = view(root, now=now, components='overview')
                    status = coverage(result)
                    page = render(root, now=now)
                shared = analyze(root, now=now)['current'].loc[lambda f:f.category.eq('global')].iloc[0]
                if pd.notna(shared.total_value):
                    self.assertEqual(status['total_value'], shared.total_value)
                else:
                    self.assertTrue(pd.isna(status['total_value']))
                self.assertIn('Sous-total connu · peut être partiel', page)
                self.assertIn('Quantités renseignées', page)
                self.assertNotIn('<th>market_value</th>', page)
                self.assertEqual(status['stale_items'], 6 if scenario=='stale' else 0)
                self.assertEqual(before,{p:p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_historical_snapshot_and_missing_snapshot_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            holdings, imported=fixture(root)
            prices=market_fixture(holdings)
            prices.to_csv(root/'data/processed/market_observations.csv',index=False)
            params={'end':'2023-02-28'}
            page=render(root,params,now='2023-04-01')
            self.assertIn('Aucun snapshot disponible',page)
            save_snapshot(holdings.assign(quantity=9),imported,'2023-02-01',root/'data/processed/global_inventory_history.csv')
            result=view(root,end='2023-02-28',now='2023-04-01',components='overview')
            self.assertEqual(coverage(result)['total_value'],540)
            self.assertIn('Consultation historique',render(root,params,now='2023-04-01'))

    def test_legacy_override_is_not_labeled_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            holdings,imported=fixture(root)
            market_fixture(holdings).to_csv(root/'data/processed/market_observations.csv',index=False)
            (root/'data/processed/steam_inventory_override.json').write_text(json.dumps(dict(schema=1,holdings=holdings.to_dict('records'),imported=list(imported))))
            page=render(root,now='2023-04-01')
            self.assertIn('Couverture non vérifiée',page)
            self.assertIn('périmètre non vérifié',page)
