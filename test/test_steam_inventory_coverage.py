import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from test_steam_inventory_import import catalog_fixture, export_fixture, owner_export_fixture
from portfolio_data import load_holdings
from steam_inventory import apply, atomic_json, preview, restore


def legacy_portfolio(root, quantity='5'):
    directory = root / 'data/processed'
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'drop_cases_inventory.csv').write_text(
        'case_name,quantity\nExample,' + quantity + '\nStored only,7\n', encoding='utf-8')


def empty_export(account='synthetic', date='2026-11-02'):
    export = export_fixture()
    export.update(account_id=account, collected_at=date)
    export['pages'][0].update(assets=[], descriptions=[])
    return export


class SteamInventoryCoverageTests(unittest.TestCase):
    def test_legacy_public_and_empty_exports_preserve_missing_and_lower_quantities(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_portfolio(root)
            before = load_holdings(root)
            csv = root / 'data/processed/drop_cases_inventory.csv'
            original = csv.read_bytes()
            for export in (export_fixture(), empty_export()):
                plan = preview(export, catalog_fixture(), root)
                self.assertEqual(plan['inventory_scope'], 'visible')
                self.assertEqual(plan['action'], 'record_visible_observation')
                self.assertEqual([row['delta'] for row in plan['changes']], [0, 0])
                differences = {row['item_name']: row for row in plan['observation_differences']}
                self.assertEqual(differences['Stored only']['status'], 'not_observed')
                self.assertIsNone(differences['Stored only']['quantity_visible'])
                self.assertEqual(differences['Stored only']['quantity_known'], 7)
                apply(export, catalog_fixture(), plan['review_token'], root, 'home')
                after = load_holdings(root)
                pd.testing.assert_frame_equal(before[0], after[0])
                self.assertEqual(before[1], after[1])
                self.assertFalse((root / 'data/processed/steam_inventory_override.json').exists())
            self.assertEqual(original, csv.read_bytes())

    def test_new_visible_items_do_not_bootstrap_or_inflate_global_portfolio(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export = export_fixture()
            plan = preview(export, catalog_fixture(), root)
            self.assertEqual(plan['holdings'], [])
            self.assertEqual(plan['imported'], [])
            self.assertEqual(plan['observed_holdings'][0]['quantity'], 2)
            self.assertEqual(plan['observation_differences'][0]['status'], 'newly_observed')
            result = apply(export, catalog_fixture(), plan['review_token'], root, 'home')
            self.assertEqual(result['inventory_scope'], 'visible')
            holdings, imported = load_holdings(root)
            self.assertTrue(holdings.empty)
            self.assertEqual(imported, set())
            files = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(result, apply(export, catalog_fixture(), plan['review_token'], root, 'home'))
            self.assertEqual(files, {p: p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_unknown_quantities_and_unmatched_public_items_remain_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_portfolio(root, '')
            export = export_fixture()
            plan = preview(export, catalog_fixture(), root)
            self.assertIsNone(plan['holdings'][0]['quantity'])
            self.assertEqual(plan['observation_differences'][0]['status'], 'known_total_unknown')
            export['pages'][0]['descriptions'][0]['market_hash_name'] = 'Unmapped visible listing'
            plan = preview(export, catalog_fixture(), root)
            result = apply(export, catalog_fixture(), plan['review_token'], root, 'home')
            self.assertEqual(result['unresolved'], ['Unmapped visible listing'])
            self.assertTrue(pd.isna(load_holdings(root)[0].quantity.iloc[0]))

    def test_catalog_resolution_can_update_the_same_observation_without_changing_holdings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_portfolio(root)
            export = export_fixture()
            incorrect_catalog = catalog_fixture()
            incorrect_catalog['market_hash_name'] = 'Other listing'
            plan = preview(export, incorrect_catalog, root)
            result = apply(export, incorrect_catalog, plan['review_token'], root, 'home')
            self.assertEqual(result['unresolved'], ['Exact Case'])
            corrected = preview(export, catalog_fixture(), root)
            result = apply(export, catalog_fixture(), corrected['review_token'], root, 'home')
            self.assertEqual(result['unresolved'], [])
            self.assertEqual(result['observed_holdings'][0]['quantity'], 2)
            self.assertEqual(load_holdings(root)[0].quantity.tolist(), [5, 7])

    def test_owner_export_explicitly_replaces_and_visible_observation_preserves_override_and_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_portfolio(root)
            export = owner_export_fixture()
            plan = preview(export, catalog_fixture(), root)
            self.assertEqual(plan['action'], 'replace_portfolio')
            apply(export, catalog_fixture(), plan['review_token'], root, 'home')
            override = root / 'data/processed/steam_inventory_override.json'
            original = override.read_bytes()
            visible = empty_export()
            plan = preview(visible, catalog_fixture(), root)
            apply(visible, catalog_fixture(), plan['review_token'], root, 'home')
            self.assertEqual(original, override.read_bytes())
            self.assertEqual(load_holdings(root)[0].quantity.tolist(), [2])
            restore(root, 'home')
            self.assertEqual(load_holdings(root)[0].quantity.tolist(), [5, 7])
            # Observations are still present but are never read as holdings.
            self.assertTrue((root / 'data/processed/steam_inventory_visible.json').exists())

    def test_scope_provenance_and_review_token_cannot_silently_promote_public_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for updates in ({'inventory_scope': 'full_portfolio'},
                            {'inventory_scope': 'full_portfolio', 'source': 'steam_community'},
                            {'inventory_scope': 'unknown'}, {'source': 'unknown'}, {'schema': True}):
                with self.subTest(updates=updates), self.assertRaises(ValueError):
                    preview(dict(export_fixture(), **updates), catalog_fixture(), root)
            second = owner_export_fixture()
            second['account_id'] = 'second'
            with self.assertRaisesRegex(ValueError, 'mix'):
                preview(dict(schema=2, complete=True, accounts=[export_fixture(), second]), catalog_fixture(), root)
            visible_plan = preview(export_fixture(), catalog_fixture(), root)
            with self.assertRaisesRegex(ValueError, 'token'):
                apply(owner_export_fixture(), catalog_fixture(), visible_plan['review_token'], root, 'home')
            with self.assertRaisesRegex(ValueError, 'school'):
                apply(export_fixture(), catalog_fixture(), visible_plan['review_token'], root)
            self.assertFalse((root / 'data/processed').exists())
            self.assertFalse((root / 'data/imports').exists())

    def test_two_accounts_and_transfer_remain_one_portfolio_without_cached_additions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_portfolio(root)
            main = empty_export('main', '2026-11-01')
            secondary = dict(export_fixture(), account_id='secondary')
            bundle = dict(schema=2, complete=True, accounts=[main, secondary])
            plan = preview(bundle, catalog_fixture(), root)
            self.assertEqual(plan['observed_holdings'][0]['quantity'], 2)
            apply(bundle, catalog_fixture(), plan['review_token'], root, 'home')
            # The next capture sees the same quantity on main after a transfer.
            # Its changed asset ID is not evidence of a second acquisition.
            transferred = dict(export_fixture(), account_id='main', collected_at='2026-11-03')
            transferred['pages'][0]['assets'][0]['assetid'] = '999'
            plan = preview(transferred, catalog_fixture(), root)
            result = apply(transferred, catalog_fixture(), plan['review_token'], root, 'home')
            self.assertEqual(result['account_ids'], ['main'])
            self.assertEqual(result['observed_holdings'][0]['quantity'], 2)
            self.assertEqual(load_holdings(root)[0].quantity.tolist(), [5, 7])
            # Omitted secondary is not deleted; its capture date remains a guard.
            older = empty_export('secondary', '2026-10-31')
            old_plan = preview(older, catalog_fixture(), root)
            with self.assertRaisesRegex(ValueError, 'older'):
                apply(older, catalog_fixture(), old_plan['review_token'], root, 'home')
            files = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            transferred['collected_at'] = '2026-11-04'
            with self.assertRaisesRegex(ValueError, 'token'):
                apply(transferred, catalog_fixture(), plan['review_token'], root, 'home')
            self.assertEqual(files, {p: p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_old_overrides_stay_readable_and_observation_write_failure_preserves_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_portfolio(root)
            old, imported = load_holdings(root)
            path = root / 'data/processed/steam_inventory_override.json'
            # A pre-fix override has no scope metadata. Do not infer/rewrite history.
            atomic_json(dict(schema=1, holdings=old.to_dict(orient='records'), imported=sorted(imported)), path)
            before = path.read_bytes()
            export = export_fixture()
            plan = preview(export, catalog_fixture(), root)
            self.assertEqual(plan['portfolio_basis'], 'legacy_override_coverage_unverified')
            apply(export, catalog_fixture(), plan['review_token'], root, 'home')
            visible_path = root / 'data/processed/steam_inventory_visible.json'
            visible_before = visible_path.read_bytes()
            export['collected_at'] = '2026-11-03'
            plan = preview(export, catalog_fixture(), root)
            real_atomic = atomic_json
            def fail_observation(value, target):
                if target == visible_path:
                    raise OSError('disk failure')
                real_atomic(value, target)
            with patch('steam_inventory.atomic_json', side_effect=fail_observation):
                with self.assertRaises(OSError):
                    apply(export, catalog_fixture(), plan['review_token'], root, 'home')
            self.assertEqual(before, path.read_bytes())
            self.assertEqual(visible_before, visible_path.read_bytes())
            pd.testing.assert_frame_equal(old, load_holdings(root)[0])

    def test_school_cli_explains_visibility_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_portfolio(root)
            source = root / 'export.json'
            source.write_text(json.dumps(empty_export()), encoding='utf-8')
            catalog = root / 'catalog.csv'
            catalog_fixture().to_csv(catalog, index=False)
            files = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            command = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'src/steam_inventory.py'),
                                      'school', '--root', str(root), '--export', str(source), '--catalog', str(catalog)],
                                     check=True, capture_output=True, text=True)
            plan = json.loads(command.stdout)
            self.assertEqual(plan['action'], 'record_visible_observation')
            self.assertIn('storage', plan['coverage_note'])
            self.assertEqual(files, {p: p.read_bytes() for p in root.rglob('*') if p.is_file()})
