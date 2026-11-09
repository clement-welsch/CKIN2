import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from catalog_import import prepare_catalog
from market_universe import validate_release


def source():
    return [dict(id=f'skin-example-{index}', market_hash_name=name, weapon=dict(id='synthetic_weapon'),
                 wear=dict(name='Factory New'), stattrak=stattrak, souvenir=souvenir)
            for index, (name, stattrak, souvenir) in enumerate([
                ('★ Example | Émeraude (Factory New)', False, False),
                ('StatTrak™ Example | Émeraude (Factory New)', True, False),
                ('Souvenir Example | Émeraude (Factory New)', False, True)])]


def prepare(records, ids=None):
    return prepare_catalog(json.dumps(records, ensure_ascii=False).encode('utf-8'),
                           ids if ids is not None else [row['id'] for row in records], revision='a'*40,
                           source_updated_at='2026-11-01', collected_at='2026-11-09')


class CatalogImportTests(unittest.TestCase):
    def test_exact_variants_unicode_hash_and_measured_file_selection(self):
        records = source()
        before = copy.deepcopy(records)
        with patch('socket.create_connection', side_effect=AssertionError('Network forbidden')):
            result = prepare(records, [records[0]['id'], records[2]['id']])
        frame = validate_release(result['release'])
        self.assertEqual(frame.market_hash_name.tolist(), [records[0]['market_hash_name'], records[2]['market_hash_name']])
        self.assertEqual(frame.category.tolist(), ['skin', 'souvenir'])
        self.assertEqual(frame.variant.tolist(), ['normal', 'souvenir'])
        self.assertEqual(result['coverage']['source_records'], 3)
        self.assertEqual(result['coverage']['selected_records'], 2)
        self.assertEqual(before, records)
        self.assertEqual(prepare(records)['release']['items'][1]['variant'], 'stattrak')
        self.assertNotIn('quantity', result['release']['items'][0])

    def test_invalid_selection_metadata_and_duplicate_identities_fail(self):
        for ids in ([], ['absent'], ['skin-example-0', 'skin-example-0']):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                prepare(source(), ids)
        for field, value in [('market_hash_name', ''), ('wear', None), ('stattrak', 'false'), ('souvenir', 1)]:
            records = source()
            records[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                prepare(records)
        records = source()
        records.append(records[0])
        with self.assertRaises(ValueError):
            prepare(records, ['skin-example-0'])
        records = source()
        records[1]['market_hash_name'] = records[0]['market_hash_name']
        with self.assertRaises(ValueError):
            prepare(records)

    def test_school_cli_is_read_only_and_produces_a_valid_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, selection = root / 'source.json', root / 'selection.json'
            path.write_text(json.dumps(source(), ensure_ascii=False), encoding='utf-8')
            selection.write_text(json.dumps(['skin-example-0']), encoding='utf-8')
            before = {p: p.read_bytes() for p in root.iterdir()}
            result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'src/catalog_import.py'),
                                     'school', '--source', str(path), '--selection', str(selection), '--revision', 'a'*40,
                                     '--source-updated-at', '2026-11-01', '--collected-at', '2026-11-09'],
                                    capture_output=True, text=True, check=True)
            validate_release(json.loads(result.stdout)['release'])
            self.assertEqual(before, {p: p.read_bytes() for p in root.iterdir()})
