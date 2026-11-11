import copy
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from steam_history_study import analyze_capture, history_time


def sample():
    path = Path(__file__).resolve().parents[1] / 'config/steam-history-study.synthetic.json'
    return json.loads(path.read_text(encoding='utf-8'))


class SteamHistoryStudyTests(unittest.TestCase):
    def test_malformed_url_types_success_flags_and_volume_digits_are_rejected(self):
        for field in ('listing_url', 'response_url'):
            for value in (None, 42, True, [], {}, '', 'https://[broken', '\n'+sample()[field], sample()[field]+'\t'):
                capture=sample();capture[field]=value
                with self.subTest(field=field,value=value), self.assertRaises(ValueError):
                    analyze_capture(capture)
        for value in (False, 0, 1.0, '1', None, [], {}):
            capture=sample();capture['response']['success']=value
            with self.subTest(success=value), self.assertRaises(ValueError):
                analyze_capture(capture)
        for value in (True, 1):
            capture=sample();capture['response']['success']=value
            self.assertEqual(analyze_capture(capture)['points'],2)
        for value in ('١٢', '１２', '1,２３４', True, 1.5):
            capture=sample();capture['response']['prices'][0][2]=value
            with self.subTest(volume=value), self.assertRaises(ValueError):
                analyze_capture(capture)

    def test_cli_rejects_malformed_captures_without_traceback_or_writes(self):
        script=Path(__file__).resolve().parents[1]/'src/steam_history_study.py'
        malformed=dict(sample(),listing_url=42)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'capture.json'
            for content in ('{', json.dumps(malformed)):
                path.write_text(content,encoding='utf-8')
                result=subprocess.run([sys.executable,str(script),'school','--capture',str(path)],capture_output=True,text=True)
                self.assertEqual(result.returncode,2)
                self.assertEqual(result.stdout,'')
                self.assertIn('Capture rejected:',result.stderr)
                self.assertNotIn('Traceback',result.stderr)
                self.assertEqual(path.read_text(encoding='utf-8'),content)
                self.assertEqual(list(Path(directory).iterdir()),[path])

    def test_offline_sample_preserves_gaps_currency_zero_and_unknown_live_verdict(self):
        capture = sample()
        before = copy.deepcopy(capture)
        with patch('socket.create_connection', side_effect=AssertionError('No Steam in school')):
            result = analyze_capture(capture)
        self.assertEqual(result['points'], 2)
        self.assertEqual(result['observed_interval_hours'], [48])
        self.assertEqual(result['volume_total'], 1234)
        self.assertEqual(result['rows'][1]['price'], '0')
        self.assertEqual(result['live_verdict'], 'pending')
        self.assertEqual(before, capture)
        self.assertEqual(history_time('Nov 01 2026 01: +2').isoformat(), '2026-10-31T23:00:00+00:00')

    def test_wrong_variants_currency_duplicates_future_errors_and_html_are_rejected(self):
        changes = [dict(currency='USD'), dict(market_hash_name='StatTrak Example Case'),
                   dict(response_url=sample()['response_url']+'&token=secret'),
                   dict(response='<html>login</html>'), dict(response=dict(success=False, prices=[]))]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                analyze_capture(dict(sample(), **change))
        for row in [['Nov 01 2026 01: +0', -1, '1'], ['Nov 01 2026 01: +0', 'NaN', '1'],
                    ['Nov 01 2026 01: +0', 1, '1,5'], ['Nov 01 2026 01: +0', 1, '-1'],
                    ['Nov 30 2026 01: +0', 1, '1'], ['bad date', 1, '1']]:
            capture = sample()
            capture['response']['prices'] = [row]
            with self.subTest(row=row), self.assertRaises(ValueError):
                analyze_capture(capture)
        capture = sample()
        capture['response']['prices'].append(capture['response']['prices'][0])
        with self.assertRaises(ValueError):
            analyze_capture(capture)

    def test_empty_capture_cannot_be_interpreted_as_no_sales_or_go(self):
        capture = sample()
        capture['response']['prices'] = []
        result = analyze_capture(capture)
        self.assertEqual(result['status'], 'empty_sample')
        self.assertIsNone(result['first_utc'])
        self.assertEqual(result['live_verdict'], 'pending')
