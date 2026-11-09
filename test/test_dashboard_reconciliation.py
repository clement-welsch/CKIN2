import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
import sys
from urllib.error import HTTPError
from urllib.request import urlopen
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from dashboard import make_server
from dashboard_reconciliation import reconcile, render_reconciliation
from portfolio_data import load_holdings
from steam_inventory import apply, preview
from test_steam_inventory_import import catalog_fixture, export_fixture
from test_steam_inventory_coverage import legacy_portfolio, empty_export


def record(root, export):
    plan = preview(export, catalog_fixture(), root)
    return apply(export, catalog_fixture(), plan['review_token'], root, 'home')


def files(root):
    return {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}


class ReconciliationTests(unittest.TestCase):
    def test_stored_absent_unknown_and_exact_identities_are_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_portfolio(root, '')
            record(root, export_fixture())
            before = files(root)
            with patch('urllib.request.urlopen', side_effect=AssertionError('network')), patch('steam_inventory.apply', side_effect=AssertionError('write')):
                result = reconcile(root)
                rows = {r['item_name']: r for r in result['rows']}
                self.assertEqual(rows['Example']['status'], 'known_total_unknown')
                self.assertIsNone(rows['Example']['quantity_known'])
                self.assertEqual(rows['Stored only']['status'], 'not_observed')
                self.assertIsNone(rows['Stored only']['quantity_visible'])
                page = render_reconciliation(root)
            self.assertIn('Inconnue', page)
            self.assertIn('jamais vendu', page)
            self.assertIn(catalog_fixture().iloc[0].item_id, page)
            self.assertEqual(before, files(root))

    def test_all_comparison_statuses_and_empty_capture(self):
        for known, amount, status in [('5', '2', 'visible_below_known'), ('2', '2', 'visible_matches_known'), ('1', '2', 'visible_exceeds_known')]:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                legacy_portfolio(root, known)
                record(root, export_fixture())
                self.assertEqual(next(r for r in reconcile(root)['rows'] if r['item_name'] == 'Example')['status'], status)
                record(root, empty_export())
                self.assertTrue(all(r['quantity_visible'] is None for r in reconcile(root)['rows']))
                self.assertEqual(load_holdings(root)[0].quantity.iloc[0], int(known))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIn('Aucune observation', render_reconciliation(root))
            self.assertEqual(files(root), {})
            record(root, export_fixture())
            self.assertEqual(reconcile(root)['rows'][0]['status'], 'newly_observed')
            self.assertIsNone(reconcile(root)['rows'][0]['quantity_known'])

    def test_two_accounts_subselection_omission_and_secondary_to_primary_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_portfolio(root, '5')
            main, secondary = export_fixture(), export_fixture()
            main['account_id'] = 'principal'
            secondary.update(account_id='secondaire', collected_at='2026-11-02')
            secondary['pages'][0]['assets'][0]['amount'] = '3'
            record(root, dict(schema=2, complete=True, accounts=[main, secondary]))
            self.assertTrue(reconcile(root)['staggered'])
            row = next(r for r in reconcile(root)['rows'] if r['item_name'] == 'Example')
            self.assertEqual((row['quantity_known'], row['quantity_visible']), (5, 5))
            one = reconcile(root, 'principal')
            self.assertEqual(next(r for r in one['rows'] if r['item_name'] == 'Example')['quantity_visible'], 2)
            self.assertIn('secondaire', one['omitted'])
            self.assertIn('Dates de capture décalées', render_reconciliation(root))
            # New main-only capture after moving objects; never add cached secondary.
            main['collected_at'] = '2026-11-03'
            main['pages'][0]['assets'][0]['amount'] = '5'
            record(root, main)
            result = reconcile(root)
            self.assertEqual(next(r for r in result['rows'] if r['item_name'] == 'Example')['quantity_visible'], 5)
            self.assertIn('secondaire', result['omitted'])
            self.assertIn('Aucun transfert', render_reconciliation(root))
            with self.assertRaises(ValueError):
                reconcile(root, 'secondaire')

    def test_unresolved_escaped_and_invalid_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export = export_fixture()
            export['pages'][0]['descriptions'][0]['market_hash_name'] = '<script>alert(1)</script>'
            record(root, export)
            page = render_reconciliation(root)
            self.assertIn('Correspondances non résolues', page)
            self.assertIn('&lt;script&gt;', page)
            self.assertNotIn('<script>', page)
            path = root / 'data/processed/steam_inventory_visible.json'
            original = json.loads(path.read_text())
            invalid_identity = copy.deepcopy(original)
            invalid_identity['accounts'][0]['holdings'] = [{'item_id': 'invalid', 'category': 'case', 'item_name': 'Example', 'quantity': 1}]
            variants = [dict(original, inventory_scope='full_portfolio'), dict(original, accounts=[]),
                        invalid_identity, dict(original, collected_at='invalid'),
                        dict(original, latest_account_collected_at=[])]
            for value in variants:
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    reconcile(root)

    def test_owner_and_legacy_provenance_and_mismatched_aggregate(self):
        from test_steam_inventory_import import owner_export_fixture
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record(root, owner_export_fixture())
            record(root, export_fixture())
            self.assertIn('Remplacement complet déclaré', render_reconciliation(root))
            path = root / 'data/processed/steam_inventory_override.json'
            value = json.loads(path.read_text())
            value.pop('inventory_scope')
            path.write_text(json.dumps(value))
            self.assertIn('couverture non vérifiée', render_reconciliation(root))
            capture_path = root / 'data/processed/steam_inventory_visible.json'
            value = json.loads(capture_path.read_text())
            value['observed_holdings'][0]['quantity'] = 999
            capture_path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                reconcile(root)

    def test_http_route_is_independent_of_invalid_optional_prices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_portfolio(root)
            record(root, export_fixture())
            (root / 'data/processed/market_observations.csv').write_text('invalid')
            before = files(root)
            server = make_server(root, 0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                url = f'http://127.0.0.1:{server.server_port}/reconciliation'
                with urlopen(url) as response:
                    self.assertEqual(response.headers['Cache-Control'], 'no-store')
                    page = response.read().decode()
                    self.assertIn('Quantité visible', page)
                    self.assertIn('tabindex="0"', page)
                for query in ('?account=absent', '?end=2026-01-01', '?account=a&account=b'):
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(url + query)
                    caught.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                worker.join()
            self.assertEqual(before, files(root))
