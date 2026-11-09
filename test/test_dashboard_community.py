import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from community_signals import extract
from dashboard import render
from portfolio_data import PRICES
from test_community_signals import corpus_fixture


class DashboardCommunityTests(unittest.TestCase):
    def test_absent_corpus_and_unverified_channels_remain_explicit(self):
        with tempfile.TemporaryDirectory() as directory, patch('socket.create_connection', side_effect=AssertionError('Network forbidden')):
            root = Path(directory)
            html = render(root, {'page': 'community'}, now='2024-07-01')
            self.assertIn('No local corpus', html)
            self.assertIn('Utilité prédictive non démontrée', html)
            self.assertFalse(list(root.rglob('*')))

    def test_populated_partial_corpus_filters_and_future_annotations_are_read_only(self):
        with tempfile.TemporaryDirectory() as directory, patch('socket.create_connection', side_effect=AssertionError('Network forbidden')):
            root = Path(directory)
            corpus = root / 'data/community'
            corpus.mkdir(parents=True)
            manifest, aliases, catalog = corpus_fixture(corpus)
            manifest['channels'].append(dict(name='<script>unverified</script>', verified=False))
            unavailable = dict(manifest['videos'][0], video_id='b'*11,
                               url='https://www.youtube.com/watch?v=' + 'b'*11,
                               status='missing_transcript')
            manifest['videos'].append(unavailable)
            aliases[0]['kind'] = 'ambiguous'
            signals, _ = extract(manifest, aliases, catalog, corpus)
            (corpus / 'annotations.json').write_text(json.dumps({signals.signal_id.iloc[0]:
                dict(annotated_at='2025-01-01', direction='up', arguments=['FUTURE_SECRET'], verified_facts=[])}), encoding='utf-8')
            (corpus / 'corpus.json').write_text(json.dumps(manifest), encoding='utf-8')
            (corpus / 'aliases.json').write_text(json.dumps(aliases), encoding='utf-8')
            processed = root / 'data/processed'
            processed.mkdir()
            catalog.to_csv(processed / 'market_catalog.csv', index=False)
            market = root / 'data/market'
            market.mkdir()
            item = catalog.iloc[0]
            prices = pd.DataFrame([dict(date=date, item_id=item.item_id, item_name=item.item_name, category=item.category,
                                       unit_price=i+1, source='steam', currency='EUR', date_estimated=False)
                                   for i, date in enumerate(pd.date_range('2023-01-31', periods=18, freq='ME'))], columns=PRICES)
            prices.to_csv(market / 'observations.csv', index=False)
            before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            html = render(root, {'page': 'community'}, now='2024-07-01')
            self.assertIn('ambiguous', html)
            self.assertIn('missing_transcript', html)
            self.assertIn('&amp;t=12s', html)
            self.assertIn('community_model', html)
            self.assertIn('&lt;script&gt;unverified', html)
            self.assertNotIn('FUTURE_SECRET', html)
            self.assertNotIn('Ignore all previous instructions', html)
            historical = render(root, {'page': 'community', 'end': '2023-01-15'}, now='2024-07-01')
            self.assertNotIn('&amp;t=12s', historical)
            filtered = render(root, {'page': 'community', 'category': 'skin'}, now='2024-07-01')
            self.assertNotIn('&amp;t=12s', filtered)
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob('*') if p.is_file()})
