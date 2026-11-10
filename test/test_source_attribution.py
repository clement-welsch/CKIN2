from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dashboard import make_server
from source_attribution import LICENSE_PATH, REVISION, SOURCE, sources_page


class SourceAttributionTests(unittest.TestCase):
    def test_offline_page_preserves_license_and_distinguishes_actual_revision(self):
        self.assertEqual(sha256(LICENSE_PATH.read_bytes()).hexdigest(),
                         "6fa98b8af7389dcc227d4f000994d235844dc653534cd5d5bff29de0aa50d88d")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIn("Aucune release", sources_page(root))
            releases = root / "data/market/releases"
            releases.mkdir(parents=True)
            for key, revision in [("known", REVISION), ("unknown", "<script>bad</script>")]:
                (releases / (key + ".json")).write_text(json.dumps(dict(source_url=SOURCE, source_revision=revision, collected_at="2026-11-04")), encoding="utf-8")
            before = {p: p.read_bytes() for p in root.rglob("*.json")}
            page = sources_page(root)
            self.assertIn("Copyright (c) 2023 ByMykel", page)
            self.assertIn("Revue de licence à vérifier", page)
            self.assertNotIn("<script>bad</script>", page)
            self.assertIn("&lt;script&gt;", page)
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*.json")})

    def test_sources_http_does_not_require_valid_portfolio_or_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad = root / "data/processed"
            bad.mkdir(parents=True)
            (bad / "skins_inventory.csv").write_text("invalid", encoding="utf-8")
            releases=root/"data/market/releases"
            releases.mkdir(parents=True)
            (releases/"corrupt.json").write_text("{")
            server = make_server(root, 0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/sources") as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    page=response.read().decode()
                    self.assertIn("ByMykel", page)
                    self.assertIn("Release locale illisible", page)
            finally:
                server.shutdown()
                server.server_close()
                worker.join()
