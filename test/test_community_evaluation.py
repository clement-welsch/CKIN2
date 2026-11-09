import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from community_evaluation import evaluate_extraction
from community_signals import extract, research
from dashboard import render
from test_community_signals import corpus_fixture


class CommunityEvaluationTests(unittest.TestCase):
    def test_reviewed_negatives_missed_mentions_and_unreviewed_passages(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, aliases, catalog = corpus_fixture(Path(directory))
            signals, _ = extract(manifest, aliases, catalog, directory)
            extra = signals.copy()
            extra['start_seconds'] = 30
            ignored = signals.copy()
            ignored['start_seconds'] = 90
            predictions = pd.concat([signals, signals, extra, ignored])
            item = catalog.item_id.iloc[0]
            def passage(offset, expected):
                return dict(video_id='a'*11, start_seconds=offset, reviewed_at='2023-02-01', expected=expected)
            expected = [dict(item_id=item, match_kind='exact')]
            sample = dict(schema=1, passages=[passage(12.5, expected), passage(30, []), passage(60, expected)])
            result = evaluate_extraction(predictions, sample, catalog, '2023-03-01')
            self.assertEqual((result['true_positives'], result['false_positives'], result['false_negatives']), (1, 1, 1))
            self.assertEqual(result['precision'], .5)
            self.assertEqual(result['recall'], .5)
            self.assertEqual(result['f1'], .5)
            self.assertEqual(result['reviewed_passages'], 3)
            deferred = evaluate_extraction(predictions, sample, catalog, '2023-01-31')
            self.assertEqual(deferred['deferred_passages'], 3)
            self.assertIsNone(deferred['precision'])
            self.assertIsNone(deferred['recall'])
            broken = copy.deepcopy(sample)
            broken['passages'].append(broken['passages'][0])
            with self.assertRaises(ValueError):
                evaluate_extraction(predictions, broken, catalog, '2023-03-01')

    def test_match_kind_is_part_of_the_label_and_zero_denominators_stay_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, aliases, catalog = corpus_fixture(Path(directory))
            signals, _ = extract(manifest, aliases, catalog, directory)
            passage = dict(video_id='a'*11, start_seconds=12.5, reviewed_at='2023-02-01',
                           expected=[dict(item_id=catalog.item_id.iloc[0], match_kind='ambiguous')])
            result = evaluate_extraction(signals, dict(schema=1, passages=[passage]), catalog, '2023-03-01')
            self.assertEqual(result['true_positives'], 0)
            self.assertEqual(result['false_positives'], 1)
            self.assertEqual(result['false_negatives'], 1)
            self.assertEqual(result['by_match_kind']['exact']['false_positives'], 1)
            self.assertEqual(result['by_match_kind']['ambiguous']['false_negatives'], 1)
            self.assertIsNone(result['by_match_kind']['family']['f1'])
            self.assertEqual(result['errors']['false_positives'][0]['match_kind'], 'exact')
            self.assertEqual(result['errors']['false_negatives'][0]['match_kind'], 'ambiguous')
            self.assertTrue(result['errors']['false_negatives'][0]['evidence_url'].endswith('&t=12s'))
            empty = evaluate_extraction(signals, dict(schema=1, passages=[]), catalog, '2023-03-01')
            self.assertIsNone(empty['f1'])
            self.assertEqual(empty['errors'], dict(false_positives=[], false_negatives=[]))

    def test_research_and_dashboard_load_sample_without_exposing_transcripts_or_writing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / 'data/community'
            corpus.mkdir(parents=True)
            manifest, aliases, catalog = corpus_fixture(corpus)
            for name, value in [('corpus', manifest), ('aliases', aliases), ('evaluation', dict(schema=1, passages=[
                dict(video_id='a'*11, start_seconds=12.5, reviewed_at='2023-02-01', expected=[
                    dict(item_id=catalog.item_id.iloc[0], match_kind='exact')])]))]:
                (corpus / (name + '.json')).write_text(json.dumps(value), encoding='utf-8')
            processed = root / 'data/processed'
            processed.mkdir()
            catalog.to_csv(processed / 'market_catalog.csv', index=False)
            before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(research(root, as_of='2023-03-01')['evaluation']['precision'], 1)
            html = render(root, {'page': 'community'}, now='2023-03-01')
            self.assertIn('Qualité de l’extraction', html)
            self.assertIn('sample_hash', html)
            self.assertNotIn('Ignore all previous instructions', html)
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob('*') if p.is_file()})
