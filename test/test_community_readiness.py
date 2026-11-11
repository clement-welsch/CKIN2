from pathlib import Path
import copy
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from community_readiness import readiness
from test_community_signals import corpus_fixture


class CommunityReadinessTests(unittest.TestCase):
    def test_eligibility_uses_imported_nonempty_transcripts_at_cutoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            corpus=root/'data/community';corpus.mkdir(parents=True)
            manifest,aliases,catalog=corpus_fixture(corpus)
            (corpus/'aliases.json').write_text(json.dumps(aliases))
            processed=root/'data/processed';processed.mkdir()
            catalog.to_csv(processed/'market_catalog.csv',index=False)
            original=copy.deepcopy(manifest['videos'][0])
            for character,changes in [
                ('b',dict(transcript_path='absent.txt')),
                ('c',dict(status='unavailable')),
                ('d',dict(collected_at='2027-01-01')),
                ('e',dict(published_at='2027-01-01',collected_at='2027-01-02')),
                ('f',dict(transcript_path='empty.txt')),
            ]:
                video=dict(original,video_id=character*11,url='https://www.youtube.com/watch?v='+character*11,**changes)
                manifest['videos'].append(video)
            (corpus/'empty.txt').write_text('   ')
            def eligibility():
                (corpus/'corpus.json').write_text(json.dumps(manifest))
                before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
                with patch('socket.socket',side_effect=AssertionError('network')):
                    result=readiness(root,'2026-11-11')
                self.assertEqual(before,{p:p.read_bytes() for p in root.rglob('*') if p.is_file()})
                return next(row for row in result['checks'] if row['requirement']=='eligible_transcripts')
            row=eligibility()
            self.assertTrue(row['ready'])
            self.assertTrue(row['detail'].startswith('1 '))
            (corpus/'sample.srt').write_text('1\n00:00:01,000 --> 00:00:02,000\nNo catalog mention here.\n')
            self.assertTrue(eligibility()['ready'])
            (corpus/'sample.srt').unlink()
            row=eligibility()
            self.assertFalse(row['ready'])
            self.assertTrue(row['detail'].startswith('0 '))

    def test_absent_invalid_and_unverified_corpus_stay_blocked_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch('socket.socket',side_effect=AssertionError('network')):
                self.assertEqual(readiness(root,'2026-11-09')['status'],'blocked')
                self.assertFalse(list(root.rglob('*')))
                corpus=root/'data/community';corpus.mkdir(parents=True)
                manifest,aliases,catalog=corpus_fixture(corpus)
                (corpus/'corpus.json').write_text(json.dumps(manifest))
                (corpus/'aliases.json').write_text(json.dumps(aliases))
                processed=root/'data/processed';processed.mkdir();catalog.to_csv(processed/'market_catalog.csv',index=False)
                before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
                result=readiness(root,'2026-11-09')
                self.assertEqual(result['status'],'blocked')
                self.assertEqual(result['predictive_benefit'],'not_established')
                self.assertTrue(any(not row['ready'] for row in result['checks']))
                self.assertEqual(before,{p:p.read_bytes() for p in root.rglob('*') if p.is_file()})
                (corpus/'corpus.json').write_text('{')
                self.assertEqual(readiness(root,'2026-11-09')['status'],'invalid_corpus')
