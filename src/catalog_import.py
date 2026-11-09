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


def audit_catalog(raw_bytes, *, revision, source_updated_at, collected_at):
    """Inspect supplied records without selecting, publishing or fetching listings.

    Reuse the import contract per record. Duplicate source/listing identities
    exclude all affected records so that file order cannot choose a winner.
    """
    payload = json.loads(raw_bytes.decode('utf-8-sig'))
    if not isinstance(payload, list) or not payload:
        raise ValueError('Expected nonempty skins_not_grouped JSON array')
    # Validate provenance even if every source record is unusable.
    if not isinstance(revision, str) or not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Expected exact lowercase upstream commit SHA')
    from market_universe import timestamp
    import pandas as pd
    updated, captured = timestamp(source_updated_at), timestamp(collected_at)
    if pd.isna(updated) or pd.isna(captured) or updated > captured:
        raise ValueError('Expected ordered source and collection timestamps')
    source_counts, identity_counts, rows = {}, {}, []
    for index, record in enumerate(payload):
        key = record.get('id') if isinstance(record, dict) else None
        if isinstance(key, str):
            source_counts[key] = source_counts.get(key, 0) + 1
        row = dict(index=index, source_id=key if isinstance(key, str) else None)
        try:
            result = prepare_catalog(json.dumps([record], ensure_ascii=False).encode('utf-8'), [key],
                                     revision=revision, source_updated_at=source_updated_at, collected_at=collected_at)
            item = result['release']['items'][0]
            row.update(item_id=item['item_id'], category=item['category'], wear=item['wear'], variant=item['variant'])
            identity_counts[item['item_id']] = identity_counts.get(item['item_id'], 0) + 1
        except (ValueError, KeyError, TypeError) as error:
            row['reason'] = str(error)
        rows.append(row)
    for row in rows:
        reasons = [row['reason']] if 'reason' in row else []
        if row['source_id'] is not None and source_counts[row['source_id']] > 1:
            reasons.append('Duplicate source ID')
        if 'item_id' in row and identity_counts[row['item_id']] > 1:
            reasons.append('Duplicate catalog identity')
        row.update(eligible=not reasons, reasons=reasons)
        row.pop('reason', None)
    eligible = [row for row in rows if row['eligible']]
    return dict(source_sha256=sha256(raw_bytes).hexdigest(), source_revision=revision,
                source_updated_at=source_updated_at, collected_at=collected_at,
                source_records=len(rows), eligible_records=len(eligible), rejected_records=len(rows)-len(eligible),
                eligible_source_ids=sorted(row['source_id'] for row in eligible), records=rows,
                counts_by_variant={kind: sum(row['variant'] == kind for row in eligible)
                                   for kind in ('normal', 'stattrak', 'souvenir')},
                limits='Local file audit only; eligibility is not human review, upstream authentication, '
                       'market completeness, tradability or price availability. No selection is published.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=['school'])
    parser.add_argument('--source', required=True, type=Path)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument('--selection', type=Path, help='JSON list of reviewed exact variant source IDs')
    operation.add_argument('--audit', action='store_true', help='Report source eligibility without preparing a release')
    parser.add_argument('--revision', required=True)
    parser.add_argument('--source-updated-at', required=True)
    parser.add_argument('--collected-at', required=True)
    args = parser.parse_args()
    metadata = dict(revision=args.revision, source_updated_at=args.source_updated_at, collected_at=args.collected_at)
    raw = args.source.read_bytes()
    result = (audit_catalog(raw, **metadata) if args.audit else
              prepare_catalog(raw, json.loads(args.selection.read_text(encoding='utf-8')), **metadata))
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
