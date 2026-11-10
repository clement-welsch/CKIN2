from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from community_readiness import readiness
from test_community_signals import corpus_fixture


class CommunityReadinessTests(unittest.TestCase):
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
