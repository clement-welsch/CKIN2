"""Exercise Steam collection using subprocess fixtures, never the network."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import update_drop_cases as collector


def response(body, status="200", returncode=0):
    return Mock(stdout=body + "\n" + status, stderr="curl failure", returncode=returncode)


def price_response(price):
    return response(json.dumps({"success": True, "lowest_price": price}))


class SteamCollectionTests(unittest.TestCase):
    def collect(self, result, name="Alpha"):
        with patch.object(collector.subprocess, "run", return_value=result) as run, redirect_stdout(StringIO()):
            price = collector.connect_to_steam(name)
        return price, run

    def test_decimal_thousands_and_zero_prices(self):
        for text, expected in [
            ("1,25 €", 1.25), ("1.25€", 1.25), ("1 234,56 €", 1234.56),
            ("1\u00a0234,56€", 1234.56), ("1\u202f234,56€", 1234.56),
            ("1.234,56€", 1234.56), ("1,234.56€", 1234.56),
            ("1.234€", 1234.0), ("1,234€", 1234.0), ("0,00€", 0.0),
            ("1.234.567,89€", 1234567.89), ("1,234,567.89€", 1234567.89),
        ]:
            with self.subTest(text=text):
                self.assertEqual(self.collect(price_response(text))[0], expected)

    def test_request_encodes_case_names_and_keeps_terminal_suffix(self):
        for name, market_name in [("Alpha & Beta", "Alpha & Beta Case"), ("Genesis Terminal", "Genesis Terminal")]:
            with self.subTest(name=name):
                _, run = self.collect(price_response("2,50€"), name)
                args, kwargs = run.call_args
                query = parse_qs(urlparse(args[0][-1]).query)
                self.assertEqual(query, {"appid": ["730"], "currency": ["3"], "market_hash_name": [market_name]})
                self.assertEqual(kwargs["timeout"], 12)
                self.assertFalse(kwargs["check"])
                self.assertIn("--max-time", args[0])

    def test_http_curl_json_and_missing_price_failures(self):
        fixtures = [response("{}", status) for status in ("429", "403", "500", "000", "bad", "")]
        fixtures += [response("{}", returncode=7), response("invalid JSON"), response("{}"),
                     price_response(None), price_response(""), price_response("unavailable")]
        for result in fixtures:
            with self.subTest(result=result):
                self.assertIsNone(self.collect(result)[0])

    def test_absent_curl_and_timeout_return_no_price(self):
        for error in (FileNotFoundError("curl.exe"), subprocess.TimeoutExpired("curl.exe", 12)):
            with self.subTest(error=error), patch.object(collector.subprocess, "run", side_effect=error), redirect_stdout(StringIO()):
                self.assertIsNone(collector.connect_to_steam("Alpha"))

    def test_malformed_payloads_cannot_become_false_observations(self):
        payloads = [None, [], 42, "text", {"success": False, "lowest_price": "1,25€"}]
        payloads += [{"success": True, "lowest_price": price} for price in (
            False, 3.5, {}, [], "-1,25€", "1,2,34€", "1.2€", "NaN", "inf", "9e9", "1,234,56€", "9" * 400,
        )]
        for payload in payloads:
            with self.subTest(payload=payload):
                self.assertIsNone(self.collect(response(json.dumps(payload)))[0])

    def test_transport_failures_leave_existing_history_byte_identical(self):
        for result in (response("{}", "429"), response("bad JSON"), price_response("-1,25€")):
            with self.subTest(result=result), tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
                root = Path(directory)
                inventory, history = root / "inventory.csv", root / "prices.csv"
                inventory.write_text("case_name,quantity\nAlpha,2\n", encoding="utf-8")
                original = b"date,case_name,unit_price\n2026-01-01,Alpha,1.25"
                history.write_bytes(original)
                with (
                    patch.object(collector, "INVENTORY_PATH", inventory),
                    patch.object(collector, "PRICE_HISTORY_PATH", history),
                    patch.object(collector.subprocess, "run", return_value=result),
                    redirect_stdout(StringIO()),
                ):
                    collector.main(collector.Environment.HOME)
                self.assertEqual(history.read_bytes(), original)

    def test_mixed_collection_preserves_old_prices_and_appends_only_successes(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            inventory, history = root / "inventory.csv", root / "prices.csv"
            inventory.write_text("case_name,quantity\nAlpha,2\nBeta,3\nGamma,1\n", encoding="utf-8")
            original = b"date,case_name,unit_price\n2026-01-01,Alpha,1.25\n2026-01-01,Beta,2.50\n"
            history.write_bytes(original)
            with (
                patch.object(collector, "INVENTORY_PATH", inventory),
                patch.object(collector, "PRICE_HISTORY_PATH", history),
                patch.object(collector.subprocess, "run", side_effect=[response("{}", "429"), price_response("0,00€"), price_response("3,50€")]),
                patch.object(collector.time, "sleep") as sleep,
                redirect_stdout(StringIO()),
            ):
                collector.main(collector.Environment.HOME)
            self.assertTrue(history.read_bytes().startswith(original))
            result = pd.read_csv(history)
            self.assertEqual(result.case_name.tolist(), ["Alpha", "Beta", "Beta", "Gamma"])
            self.assertEqual(result.unit_price.tolist(), [1.25, 2.5, 0.0, 3.5])
            self.assertEqual(sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
