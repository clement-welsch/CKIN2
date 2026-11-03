"""Scheduling and retry contracts without real Steam or scheduled task changes."""

from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import BytesIO, StringIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from test_multicategory_prices import fixture
from collection_runtime import CollectionBusy, RetryingSteam, collection_lock, retry_after_seconds
from scheduled_collection import config_from, scheduled, write_json
from update_portfolio import run

NOW = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)


def success():
    return BytesIO(b'{"success":true,"lowest_price":"2,50 EUR"}'.replace(b" EUR", b""))


class RetryTests(unittest.TestCase):
    def test_retry_after_and_backoff_then_success(self):
        error = HTTPError("https://example.invalid", 429, "limit", {"Retry-After": "7"}, None)
        opener = Mock(side_effect=[error, URLError("offline"), success()])
        pause = Mock()
        fetch = RetryingSteam(opener=opener, pause=pause, clock=lambda: NOW)
        self.assertEqual(fetch("PRIVATE NAME"), 2.5)
        self.assertEqual([c.args[0] for c in pause.call_args_list], [7, 4])
        self.assertEqual(fetch.outcomes, [{"kind": "updated", "attempts": 3}])

    def test_permanent_http_and_no_price_not_retried(self):
        for response, kind in [(HTTPError("https://example.invalid", 404, "missing", {}, None), "permanent_http"),
                               (BytesIO(b'{"success":false}'), "no_price")]:
            opener = Mock(side_effect=response) if isinstance(response, Exception) else Mock(return_value=response)
            fetch = RetryingSteam(opener=opener)
            with redirect_stdout(StringIO()):
                self.assertIsNone(fetch("test"))
            self.assertEqual(opener.call_count, 1)
            self.assertEqual(fetch.outcomes[0]["kind"], kind)

    def test_long_retry_after_defers_without_shortening_or_sleeping(self):
        opener = Mock(side_effect=HTTPError("https://example.invalid", 503, "busy", {"Retry-After": "600"}, None))
        pause = Mock()
        fetch = RetryingSteam(opener=opener, pause=pause, clock=lambda: NOW)
        self.assertIsNone(fetch("test"))
        pause.assert_not_called()
        self.assertEqual(opener.call_count, 1)
        self.assertEqual(fetch.outcomes[0]["retry_at"], "2026-11-03T12:10:00+00:00")
        self.assertIsNone(fetch("second listing"))
        self.assertEqual(opener.call_count, 1)
        self.assertEqual(fetch.outcomes[-1]["kind"], "deferred")

    def test_retries_are_bounded_and_http_date_is_supported(self):
        opener = Mock(side_effect=TimeoutError())
        pause = Mock()
        fetch = RetryingSteam(opener=opener, pause=pause, clock=lambda: NOW)
        self.assertIsNone(fetch("test"))
        self.assertEqual(opener.call_count, 3)
        self.assertEqual(pause.call_count, 2)
        self.assertEqual(retry_after_seconds("Tue, 03 Nov 2026 12:00:30 GMT", NOW), 30)
        self.assertEqual(retry_after_seconds("invalid", NOW), 0)


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        fixture(self.root)

    def execute(self, **kwargs):
        with redirect_stdout(StringIO()) as output:
            code = scheduled(self.root, "home", clock=lambda: NOW,
                             fetch=lambda _: 2.5, pause=lambda _: None, **kwargs)
        return code, output.getvalue()

    def test_complete_journal_cadence_privacy_and_repeated_alert_suppression(self):
        self.assertEqual(self.execute()[0], 0)
        state = self.root / "data/runtime/collection-state.json"
        contents = json.loads(state.read_text())
        self.assertEqual(contents["last_success"], NOW.isoformat())
        self.assertEqual(contents["next_due"], "2026-11-04T12:00:00+00:00")
        self.assertNotIn("Collection changed", self.execute()[1])
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertIn("not due", self.execute(due=True)[1])
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        journal = next((self.root / "data/runtime/runs").glob("*.json")).read_text()
        self.assertNotIn("Recoil", journal)
        self.assertNotIn("AK-47", journal)
        self.assertEqual(json.loads(journal)["updated"], 6)

    def test_school_writes_no_runtime_or_data_and_has_no_network(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch("update_market_prices.fetch_market_price", side_effect=AssertionError("network")), redirect_stdout(StringIO()):
            self.assertEqual(scheduled(self.root, "school"), 1)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_mutual_exclusion_and_recovery_after_process_exit(self):
        with collection_lock(self.root):
            with self.assertRaises(CollectionBusy):
                with collection_lock(self.root):
                    self.fail("second lock acquired")
            self.assertEqual(self.execute()[0], 1)
            with redirect_stdout(StringIO()):
                self.assertEqual(run(self.root, "home")["code"], 2)
        # A process that dies without cleanup must not leave a stale kernel lock.
        script = "import sys,os;sys.path.insert(0,sys.argv[1]);from collection_runtime import collection_lock;lock=collection_lock(sys.argv[2]);lock.__enter__();os._exit(0)"
        result = subprocess.run([sys.executable, "-c", script, str(Path(__file__).resolve().parents[1] / "src"), str(self.root)], timeout=20)
        self.assertEqual(result.returncode, 0)
        with collection_lock(self.root):
            pass

    def test_interrupted_run_is_detected_and_can_resume_before_due(self):
        self.execute()
        write_json(self.root / "data/runtime/collection-active.json", {"started": NOW.isoformat()})
        self.assertEqual(self.execute(due=True)[0], 0)
        events = [json.loads(p.read_text()) for p in (self.root / "data/runtime/runs").glob("*.json")]
        self.assertTrue(any(e["interrupted_previous"] for e in events))

    def test_persistent_failures_notify_only_on_condition_changes(self):
        import pandas as pd
        result = dict(code=2, stages=[dict(stage="validation", status="failed", error="PRIVATE")], collection=pd.DataFrame())
        with patch("scheduled_collection._run", return_value=result):
            outputs = [self.execute()[1] for _ in range(4)]
        self.assertIn("Collection changed", outputs[0])
        self.assertNotIn("Collection changed", outputs[1])
        self.assertIn("persistent=True", outputs[2])
        self.assertNotIn("Collection changed", outputs[3])
        for path in (self.root / "data/runtime").rglob("*.json"):
            self.assertNotIn("PRIVATE", path.read_text())

    def test_configuration_validation(self):
        path = self.root / "settings.json"
        for setting in ({"attempts": 0}, {"attempts": True}, {"base_delay_seconds": -1},
                        {"stale_days": float("inf")}, {"notification": "email"}, {"unknown": 1}):
            path.write_text(json.dumps(setting))
            with self.subTest(setting=setting), self.assertRaises(ValueError):
                config_from(path)

    def test_retry_deferral_is_saved_as_next_due_and_not_a_false_price(self):
        config = self.root / "config.json"
        config.write_text(json.dumps({"interval_minutes": 1}))
        adapter = RetryingSteam(max_wait=1, clock=lambda: NOW,
                                opener=Mock(side_effect=HTTPError("https://example.invalid", 429, "limited", {"Retry-After": "600"}, None)))
        with patch("scheduled_collection.RetryingSteam", return_value=adapter), redirect_stdout(StringIO()):
            code = scheduled(self.root, "home", config=config, clock=lambda: NOW, pause=lambda _: None)
        self.assertEqual(code, 1)
        self.assertFalse((self.root / "data/processed/market_observations.csv").exists())
        state = json.loads((self.root / "data/runtime/collection-state.json").read_text())
        self.assertEqual(state["next_due"], "2026-11-03T12:10:00+00:00")
        self.assertIsNone(state["last_success"])
        event = json.loads(next((self.root / "data/runtime/runs").glob("*.json")).read_text())
        self.assertEqual(event["outcomes"], {"temporary": 1, "deferred": 5})

    def test_invalid_catalog_is_not_retried_and_journal_has_no_raw_error(self):
        (self.root / "data/processed/market_catalog.csv").write_text("invalid\nrow\n")
        fetch = Mock(side_effect=AssertionError("network"))
        with redirect_stdout(StringIO()):
            self.assertEqual(scheduled(self.root, "home", clock=lambda: NOW, fetch=fetch), 2)
        fetch.assert_not_called()
        event = json.loads(next((self.root / "data/runtime/runs").glob("*.json")).read_text())
        self.assertEqual(event["failed_stages"], ["validation"])


if __name__ == "__main__":
    unittest.main()
