from pathlib import Path
import copy
import json
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from dashboard import render, view
from dashboard_reconciliation import reconciliation, read_observation
from steam_inventory import apply, preview
from test_steam_inventory_coverage import legacy_portfolio, empty_export
from test_steam_inventory_import import catalog_fixture, export_fixture


def record(root, export):
    plan=preview(export,catalog_fixture(),root)
    apply(export,catalog_fixture(),plan['review_token'],root,'home')


class ReconciliationTests(unittest.TestCase):
    def test_missing_empty_stored_and_unknown_quantities_are_never_zero_or_sales(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.assertIsNone(reconciliation(root,view(root,now='2026-11-04',components='reconciliation'))['capture'])
            legacy_portfolio(root, '')
            record(root,export_fixture())
            before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with patch('socket.socket',side_effect=AssertionError('network')):
                result=reconciliation(root,view(root,now='2026-11-04',components='reconciliation'))
                rows=result['rows'].set_index('item_name')
                self.assertEqual(rows.loc['Example','status'],'known_total_unknown')
                self.assertEqual(rows.loc['Stored only','status'],'not_observed')
                self.assertTrue(pd.isna(rows.loc['Stored only','quantity_visible']))
                page=render(root,{'page':'reconciliation'},now='2026-11-04')
                self.assertIn('unités de stockage',page)
            self.assertEqual(before,{p:p.read_bytes() for p in root.rglob('*') if p.is_file()})
            record(root,empty_export())
            result=reconciliation(root,view(root,now='2026-11-04',components='reconciliation'))
            self.assertTrue(result['rows'].status.eq('not_observed').all())

    def test_account_subsets_transfers_dates_and_cached_accounts_do_not_accumulate(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            legacy_portfolio(root,'5')
            first,second=export_fixture(),export_fixture()
            first.update(account_id='primary',collected_at='2026-11-01')
            second.update(account_id='secondary',collected_at='2026-11-02')
            record(root,dict(schema=2,complete=True,accounts=[first,second]))
            data=view(root,now='2026-11-04',components='reconciliation')
            combined=reconciliation(root,data)
            self.assertTrue(combined['mismatched_dates'])
            self.assertEqual(combined['rows'].set_index('item_name').loc['Example','quantity_visible'],4)
            single=reconciliation(root,data,'primary')
            self.assertEqual(single['rows'].set_index('item_name').loc['Example','quantity_visible'],2)
            self.assertIn('secondary',single['omitted'])
            # Secondary to primary transfer: only this newer selection is compared.
            first['collected_at']='2026-11-03'
            first['pages'][0]['assets'][0]['amount']='4'
            record(root,first)
            current=reconciliation(root,view(root,now='2026-11-04',components='reconciliation'))
            self.assertEqual(current['rows'].set_index('item_name').loc['Example','quantity_visible'],4)
            self.assertIn('secondary',current['omitted'])
            self.assertEqual(current['rows'].set_index('item_name').loc['Example','quantity_known'],5)
            self.assertIsNone(read_observation(root,pd.Timestamp('2026-10-01')))
            with self.assertRaises(ValueError):
                reconciliation(root,data,'missing')

    def test_new_visible_items_and_invalid_capture_do_not_create_holdings(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            record(root,export_fixture())
            data=view(root,now='2026-11-04',components='reconciliation')
            result=reconciliation(root,data)
            self.assertEqual(result['rows'].status.tolist(),['newly_observed'])
            self.assertTrue(data['detail'].loc[data['detail'].state.eq('holdings')].empty)
            path=root/'data/processed/steam_inventory_visible.json'
            value=json.loads(path.read_text())
            value['observed_holdings'][0]['quantity']=999
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                read_observation(root,pd.Timestamp('2026-11-04'))
