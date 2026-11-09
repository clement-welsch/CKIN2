"""Prepare a reviewed local ByMykel skin selection; no network or persistence."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

from market_universe import release_id, validate_release
from portfolio_data import identity


def prepare_catalog(raw_bytes, selected_ids, *, revision, source_updated_at, collected_at):
    """Import exact source variants without synthesizing names or owned quantities."""
    if not isinstance(revision, str) or not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Expected exact lowercase upstream commit SHA')
    if (not isinstance(selected_ids, list) or not selected_ids
            or not all(isinstance(key, str) and key.strip() == key and key for key in selected_ids)
            or len(set(selected_ids)) != len(selected_ids)):
        raise ValueError('Select unique reviewed source IDs explicitly')
    payload = json.loads(raw_bytes.decode('utf-8-sig'))
    if not isinstance(payload, list) or not payload:
        raise ValueError('Expected nonempty skins_not_grouped JSON array')
    records = {}
    for record in payload:
        if not isinstance(record, dict) or not isinstance(record.get('id'), str) or not record['id'].strip():
            raise ValueError('Source record requires an ID')
        if record['id'] in records:
            raise ValueError('Duplicate source ID')
        records[record['id']] = record
    if not set(selected_ids).issubset(records):
        raise ValueError('Selected source IDs are absent from this file')
    items = []
    for key in selected_ids:
        record = records[key]
        name = record.get('market_hash_name')
        wear = record.get('wear')
        if not isinstance(name, str) or not name or name != name.strip():
            raise ValueError('Selected record lacks an exact market listing')
        if not isinstance(wear, dict) or not isinstance(wear.get('name'), str) or not wear['name'].strip():
            raise ValueError('Selected record lacks explicit wear metadata')
        if type(record.get('stattrak')) is not bool or type(record.get('souvenir')) is not bool or (record['stattrak'] and record['souvenir']):
            raise ValueError('Selected record has unsupported variant flags')
        if not isinstance(record.get('weapon'), dict) or not record['weapon'].get('id'):
            raise ValueError('Only reviewed weapon/glove skin records are supported')
        category = 'souvenir' if record['souvenir'] else 'skin'
        variant = 'souvenir' if record['souvenir'] else 'stattrak' if record['stattrak'] else 'normal'
        items.append(dict(item_id=identity(category, name), category=category, item_name=name,
                          market_hash_name=name, source_id=key, wear=wear['name'], variant=variant,
                          collection=None))
    release = dict(schema=1, source_url='https://github.com/ByMykel/CSGO-API', source_revision=revision,
                   source_path='public/api/en/skins_not_grouped.json', source_sha256=sha256(raw_bytes).hexdigest(),
                   source_updated_at=source_updated_at, collected_at=collected_at,
                   scope='Explicitly reviewed exact weapon/glove skin variants; no float/pattern premiums', items=items)
    validate_release(release)
    return dict(release=release, release_id=release_id(release), coverage=dict(
        source_records=len(records), selected_records=len(items), unselected_records=len(records)-len(items),
        selected_fraction=len(items)/len(records),
        meaning='Fraction of this supplied source file only, not coverage of the Steam market. '
                'Source revision is declared by the reviewer; file hash preserves bytes but does not authenticate upstream origin. '
                'Collections are unavailable in this adapter; no membership is inferred.'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=['school'])
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--selection', required=True, type=Path, help='JSON list of reviewed exact variant source IDs')
    parser.add_argument('--revision', required=True)
    parser.add_argument('--source-updated-at', required=True)
    parser.add_argument('--collected-at', required=True)
    args = parser.parse_args()
    result = prepare_catalog(args.source.read_bytes(), json.loads(args.selection.read_text(encoding='utf-8')),
                             revision=args.revision, source_updated_at=args.source_updated_at, collected_at=args.collected_at)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
