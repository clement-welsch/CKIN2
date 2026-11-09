from pathlib import Path
import tempfile
import unittest

import pandas as pd

from dashboard import view,render
from dashboard_comparison import compare_snapshots
from global_snapshots import save_snapshot
from test_multicategory_prices import fixture
from test_global_analysis import market_fixture


class ComparisonTests(unittest.TestCase):
    def test_pair_effects_reconcile_and_identical_snapshots_remain_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);holdings,imported=fixture(root)
            market_fixture(holdings).to_csv(root/'data/processed/market_observations.csv',index=False)
            history=root/'data/processed/global_inventory_history.csv'
            save_snapshot(holdings,imported,'2023-01-31',history)
            save_snapshot(holdings.assign(quantity=3),imported,'2023-03-31',history)
            data=view(root,now='2023-04-01',components='comparison')
            result=compare_snapshots(data)
            self.assertEqual(result['delta'],result['explained'])
            self.assertEqual(result['residual'],0)
            self.assertTrue((result['rows'].price_effect+result['rows'].quantity_effect).eq(result['rows'].value_change).all())
            same=compare_snapshots(data,'2023-01-31','2023-01-31')
            self.assertEqual(same['delta'],0);self.assertEqual(same['explained'],0)
            before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertIn('Résidu calculable',render(root,{'page':'comparison','category':'case'},now='2023-04-01'))
            reset=render(root,{'page':'comparison','category':'case','comparison_before':'2020-01-01','comparison_after':'2023-03-31'},now='2023-04-01')
            self.assertIn('Choix de snapshots réinitialisé',reset)
            self.assertNotIn('2020-01-01',reset)
            self.assertEqual(before,{p:p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_unknown_quantity_and_price_zero_do_not_invent_residual(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);holdings,imported=fixture(root)
            market_fixture(holdings).assign(unit_price=0).to_csv(root/'data/processed/market_observations.csv',index=False)
            path=root/'data/processed/global_inventory_history.csv'
            save_snapshot(holdings,imported,'2023-01-31',path)
            changed=holdings.copy();changed.loc[0,'quantity']=None
            save_snapshot(changed,imported,'2023-03-31',path)
            data=view(root,now='2023-04-01',components='comparison')
            result=compare_snapshots(data)
            self.assertEqual(result['excluded'],1)
            self.assertTrue(pd.isna(result['delta']));self.assertTrue(pd.isna(result['residual']))
            self.assertEqual(result['explained'],0)
            with self.assertRaises(ValueError):compare_snapshots(data,'2023-03-31','2023-01-31')
            with self.assertRaises(ValueError):compare_snapshots(data,'2023-02-01','2023-03-31')

    def test_no_history_or_period_without_records_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            data=view(Path(directory),now='2023-04-01',components='comparison')
            self.assertEqual(compare_snapshots(data)['dates'],[])
