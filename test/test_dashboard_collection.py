import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dashboard import make_server
from dashboard_collection import PriceRefresh, CloudPublication


class RefreshTests(unittest.TestCase):
    def test_cloud_command_reports_success_and_redacts_failures(self):
        for code, output, expected in [(0, 'Cloud: Google Drive upload confirmed.', 'success'),
                                      (0, 'Cloud: archive ready', 'success'),
                                      (1, 'private-provider-response', 'error'),
                                      (2, 'private-provider-response', 'error')]:
            with self.subTest(code=code, output=output), tempfile.TemporaryDirectory() as temporary:
                cloud = CloudPublication(temporary)
                result = type('Result', (), dict(returncode=code, stdout=output, stderr='private-secret'))()
                with patch('dashboard_collection.subprocess.run', return_value=result) as command:
                    cloud._run()
                self.assertEqual(command.call_args.args[0][-3:], ['publish', '--root', str(Path(temporary).resolve())])
                self.assertEqual(cloud.status()['state'], expected)
                self.assertNotIn('private', json.dumps(cloud.status()))
                self.assertNotIn('detail', cloud.status())

    def test_cloud_routes_require_same_origin_post_and_get_is_read_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            server = make_server(Path(temporary), 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f'http://127.0.0.1:{server.server_port}'
            try:
                with patch.object(CloudPublication, 'start', return_value=True) as start:
                    with urlopen(url + '/api/cloud-publish') as response:
                        self.assertEqual(json.load(response)['state'], 'idle')
                    with urlopen(url + '/cloud-publish.js') as response:
                        self.assertIn(b'/api/cloud-publish', response.read())
                    start.assert_not_called()
                    for headers in ({}, {'X-CKIN2-Refresh': '1', 'Origin': 'https://evil.test'}):
                        with self.assertRaises(HTTPError) as caught:
                            urlopen(Request(url + '/api/cloud-publish', data=b'', headers=headers))
                        self.assertEqual(caught.exception.code, 403)
                        caught.exception.close()
                    start.assert_not_called()
                    with urlopen(Request(url + '/api/cloud-publish', data=b'', headers={'X-CKIN2-Refresh': '1'})) as response:
                        self.assertEqual(response.status, 202)
                    start.assert_called_once()
                    start.return_value = False
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(Request(url + '/api/cloud-publish', data=b'', headers={'X-CKIN2-Refresh': '1'}))
                    self.assertEqual(caught.exception.code, 409)
                    caught.exception.close()
                self.assertFalse(list(Path(temporary).rglob('*')))
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_background_command_duplicate_and_results(self):
        for code, expected in [(0, 'success'), (1, 'partial'), (2, 'error')]:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as temporary:
                started, release = threading.Event(), threading.Event()
                def command(args, **kwargs):
                    self.assertEqual(args[-3:], ['home', '--root', str(Path(temporary).resolve())])
                    started.set()
                    release.wait(5)
                    return type('Result', (), dict(returncode=code, stdout='report', stderr=''))()
                refresh = PriceRefresh(temporary)
                with patch('dashboard_collection.subprocess.run', side_effect=command):
                    self.assertTrue(refresh.start())
                    self.assertTrue(started.wait(5))
                    self.assertFalse(refresh.start())
                    self.assertEqual(refresh.status()['state'], 'running')
                    release.set()
                    # Acquire completion without relying on collection timing.
                    for thread in threading.enumerate():
                        if getattr(thread, '_target', None) == refresh._run:
                            thread.join(5)
                    self.assertEqual(refresh.status()['state'], expected)
                    self.assertEqual(refresh.status()['detail'], 'report')

    def test_routes_require_explicit_same_origin_post(self):
        with tempfile.TemporaryDirectory() as temporary:
            server = make_server(Path(temporary), 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f'http://127.0.0.1:{server.server_port}'
            try:
                with patch.object(PriceRefresh, 'start', return_value=True) as start:
                    with urlopen(url + '/api/steam-refresh') as response:
                        self.assertEqual(json.load(response)['state'], 'idle')
                    start.assert_not_called()
                    for headers in ({}, {'X-CKIN2-Refresh': '1', 'Origin': 'https://evil.test'},
                                    {'X-CKIN2-Refresh': '1', 'Sec-Fetch-Site': 'cross-site'}):
                        with self.assertRaises(HTTPError) as caught:
                            urlopen(Request(url + '/api/steam-refresh', data=b'', headers=headers))
                        self.assertEqual(caught.exception.code, 403)
                        caught.exception.close()
                    start.assert_not_called()
                    with urlopen(Request(url + '/api/steam-refresh', data=b'', headers={
                        'X-CKIN2-Refresh': '1', 'Origin': url})) as response:
                        self.assertEqual(response.status, 202)
                    start.assert_called_once()
                    start.return_value = False
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(Request(url + '/api/steam-refresh', data=b'', headers={'X-CKIN2-Refresh': '1'}))
                    self.assertEqual(caught.exception.code, 409)
                    caught.exception.close()
                self.assertFalse(list(Path(temporary).rglob('*')))
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
