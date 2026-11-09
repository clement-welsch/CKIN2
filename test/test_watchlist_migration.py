import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_market_universe import release_fixture
from market_universe import preview_watchlist_migration, publish
from portfolio_data import identity


class WatchlistMigrationTests(unittest.TestCase):
    def test_rename_removal_and_variant_changes_require_review(self):
        old = release_fixture()
        new = copy.deepcopy(old)
        renamed = new['items'][0]
        renamed.update(item_name='renamed', item_id=identity(renamed['category'], 'renamed'), market_hash_name='renamed listing')
        new['items'][1]['wear'] = 'Factory New'
        new['items'][2]['collection'] = 'updated collection'
        new['items'].pop()
        watch = [row['item_id'] for row in old['items']]
        before = copy.deepcopy((old, new, watch))
        result = preview_watchlist_migration(old, new, watch)
        self.assertTrue(result['requires_review'])
        self.assertEqual(result['retained_watchlist'], watch[2:-1])
        self.assertEqual(result['entries'][0]['proposed_item_id'], renamed['item_id'])
        self.assertIsNone(result['entries'][-1]['proposed_item_id'])
        self.assertEqual(before, (old, new, watch))
        for invalid in ([watch[0], watch[0]], ['unknown'], 'not a list'):
            with self.assertRaises(ValueError):
                preview_watchlist_migration(old, new, invalid)
        self.assertEqual(preview_watchlist_migration(old, new, [])['retained_watchlist'], [])

    def test_school_cli_preserves_all_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release = release_fixture()
            key = publish(release, root, 'home')
            path = root / 'watchlist.json'
            watch = [release['items'][0]['item_id']]
            path.write_text(json.dumps(watch), encoding='utf-8')
            before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'src/market_universe.py'),
                                     'school', '--root', str(root), '--migrate-watchlist', key, key,
                                     '--watchlist', str(path)], check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(result.stdout)['retained_watchlist'], watch)
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob('*') if p.is_file()})
