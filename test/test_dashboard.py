from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dashboard import make_server, render, view
from global_snapshots import save_snapshot
from portfolio_data import load_holdings
from test_multicategory_prices import fixture
from test_global_analysis import market_fixture


class DashboardTests(unittest.TestCase):
    def test_empty_partial_filters_and_live_file_refresh_are_read_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            empty = render(root, now="2026-11-04")
            self.assertIn("Indisponible", empty)
            self.assertFalse(list(root.rglob("*")))
            holdings, _ = fixture(root)
            prices = market_fixture(holdings)
            prices.to_csv(root / "data/processed/market_observations.csv", index=False)
            save_snapshot(holdings, {"case", "skin", "souvenir", "sticker", "agent", "charm"}, "2023-03-31", root / "data/processed/global_inventory_history.csv")
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            data = view(root, category="case", now="2023-04-01")
            self.assertTrue(data["current"].loc[data["current"].category.eq("global"), "total_value"].notna().all())
            result = render(root, {"category": "case", "item_id": holdings.loc[holdings.category.eq("case"), "item_id"].iloc[0], "start": "2023-01-01", "end": "2023-03-31"}, now="2023-04-01")
            self.assertIn("dernier snapshot", result)
            self.assertIn("Gains et pertes", result)
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()})
            prices.loc[prices.category.eq("case"), "unit_price"] = 999
            prices.to_csv(root / "data/processed/market_observations.csv", index=False)
            self.assertIn(999, view(root, category="case", now="2023-04-01")["detail"].unit_price.tolist())

    def test_http_loopback_no_store_filters_and_mutations(self):
        with tempfile.TemporaryDirectory() as temporary:
            server = make_server(Path(temporary), 0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            url = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(url) as response:
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertIn("CKIN2", response.read().decode())
                for path in ("/?category=invalid", "/?end=invalid", "/private.csv", "/?category=case&category=skin"):
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(url + path)
                    caught.exception.close()
                with self.assertRaises(HTTPError) as caught:
                    urlopen(Request(url, headers={"Host": "evil.test"}))
                caught.exception.close()
                with self.assertRaises(HTTPError) as caught:
                    urlopen(Request(url, data=b"write", method="POST"))
                caught.exception.close()
                self.assertFalse(list(Path(temporary).rglob("*")))
            finally:
                server.shutdown()
                server.server_close()
                worker.join()
