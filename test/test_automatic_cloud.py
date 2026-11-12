import contextlib
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cloud_inventory import auto_publish, configure, publish, restore
from google_drive_cloud import folder_id, upload_archive, connect, SCOPE, SECRET_PATH
from private_cloud_state import load_private, save_private
from test_multicategory_prices import fixture
from test_steam_inventory_import import owner_export_fixture, catalog_fixture
from steam_inventory import apply, preview, restore as restore_inventory
from update_portfolio import run, PARTIAL


class AutomaticCloudTests(unittest.TestCase):
    def test_disabled_is_read_only_and_private_state_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(auto_publish(root)["status"], "disabled")
            self.assertEqual(list(root.iterdir()), [])
            secret = root / "private.secret"
            save_private(secret, {"refresh_token": "synthetic-token"})
            self.assertEqual(load_private(secret), {"refresh_token": "synthetic-token"})

    def test_google_failure_is_reported_without_private_details(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "data/runtime/cloud-config.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"enabled": True, "provider": "google_drive"}))
            from google_drive_cloud import publish_google
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = auto_publish(root)
            self.assertEqual(result["status"], "failed")
            self.assertNotIn("refresh_token", output.getvalue())
            with patch("google_drive_cloud.publish_google") as upload:
                self.assertEqual(auto_publish(root)["status"], "uploaded")
                upload.assert_called_once_with(root)

    @unittest.skipUnless(importlib.util.find_spec("google_auth_oauthlib"), "optional Google dependencies not installed")
    def test_google_consent_is_required_before_enabling_and_secrets_are_not_archived(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            client = root / "client_secret.json"
            client.write_text(json.dumps({"installed": {"auth_uri": "https://accounts.google.com/o/oauth2/auth",
                                                       "token_uri": "https://oauth2.googleapis.com/token"}}))
            flow = Mock()
            flow.run_local_server.return_value.refresh_token = "synthetic-refresh"
            flow.run_local_server.return_value.to_json.return_value = json.dumps({"refresh_token": "synthetic-refresh"})
            credentials = flow.run_local_server.return_value
            flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth?state=synthetic", "synthetic")
            def consent(**options):
                flow.authorization_url()
                self.assertTrue((root / "data/runtime/google-connect.html").exists())
                return credentials
            flow.run_local_server.side_effect = consent
            session = flow.authorized_session.return_value.__enter__ = Mock(return_value=Mock())
            flow.authorized_session.return_value.__exit__ = Mock(return_value=False)
            with patch("google_auth_oauthlib.flow.InstalledAppFlow.from_client_config", return_value=flow) as factory:
                with patch("google_drive_cloud.check_folder", side_effect=ValueError("no permission")):
                    with self.assertRaises(ValueError):
                        connect(root, client, "synthetic_folder_id")
                self.assertFalse((root / "data/runtime/cloud-config.json").exists())
                self.assertFalse((root / "data/runtime/google-connect.html").exists())
                with patch("google_drive_cloud.check_folder"):
                    connect(root, client, "synthetic_folder_id")
                self.assertEqual(factory.call_args.args[1], [SCOPE])
                self.assertTrue(factory.call_args.kwargs["autogenerate_code_verifier"])
                options = flow.run_local_server.call_args.kwargs
                self.assertEqual(options["host"], "127.0.0.1")
                self.assertEqual(options["file_ids"], "synthetic_folder_id")
                self.assertNotIn("{url}", options["authorization_prompt_message"])
            self.assertEqual(load_private(root / SECRET_PATH)["folder_id"], "synthetic_folder_id")
            self.assertFalse((root / "data/runtime/google-connect.html").exists())
            import zipfile
            archive = publish(root, root / "cloud")
            with zipfile.ZipFile(archive) as bundle:
                self.assertFalse(any("runtime" in name or "secret" in name for name in bundle.namelist()))

    def test_owner_import_retry_and_restore_publish_effective_quantities(self):
        with tempfile.TemporaryDirectory() as directory:
            root, folder = Path(directory) / "home", Path(directory) / "cloud"
            fixture(root)
            folder.mkdir()
            configure(root, folder)
            export, catalog = owner_export_fixture(), catalog_fixture()
            token = preview(export, catalog, root)["review_token"]
            apply(export, catalog, token, root, "home")
            archives = list(folder.glob("*.zip"))
            self.assertEqual(len(archives), 1)
            school = Path(directory) / "school"
            restore(archives[0], school)
            from portfolio_data import load_holdings
            expected, imported = load_holdings(root)
            actual, actual_imported = load_holdings(school)
            self.assertEqual(expected.to_dict("records"), actual.to_dict("records"))
            self.assertEqual(imported, actual_imported)
            self.assertFalse((school / "data/runtime").exists())
            restore_inventory(root, "home")
            self.assertEqual(len(list(folder.glob("*.zip"))), 2)

    def test_workflow_and_school_and_unavailable_destination(self):
        import pandas as pd
        with tempfile.TemporaryDirectory() as directory:
            root, folder = Path(directory) / "home", Path(directory) / "cloud"
            fixture(root)
            folder.mkdir()
            configure(root, folder)
            options = dict(clock=lambda: pd.Timestamp("2026-10-31T12:00:00"), fetch=lambda _: 5, pause=lambda _: None)
            with contextlib.redirect_stdout(io.StringIO()):
                result = run(root, "home", **options)
                self.assertEqual(result["stages"][-1]["status"], "ready_for_sync")
                before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
                run(root, "school", **options)
                self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()})
                missing = folder / "unmounted"
                configure(root, disabled=True)
                config = root / "data/runtime/cloud-config.json"
                config.write_text(json.dumps({"enabled": True, "folder": str(missing)}))
                result = run(root, "home", **options)
            self.assertEqual(result["code"], PARTIAL)
            self.assertEqual(result["stages"][-1]["status"], "failed")
            self.assertFalse(missing.exists())

    def test_drive_upload_verifies_bytes_and_limits_upload_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "snapshot.zip"
            archive.write_bytes(b"synthetic archive")
            session = Mock()
            session.get.return_value = Mock(status_code=200)
            session.get.return_value.json.return_value = {
                "mimeType": "application/vnd.google-apps.folder", "capabilities": {"canAddChildren": True}}
            session.post.return_value = Mock(status_code=200, headers={"Location": "https://www.googleapis.com/upload/drive/v3/files?upload_id=test"})
            session.put.return_value = Mock(status_code=200)
            session.put.return_value.json.return_value = {"id": "synthetic", "size": str(archive.stat().st_size),
                "md5Checksum": hashlib.md5(archive.read_bytes(), usedforsecurity=False).hexdigest()}
            upload_archive(session, archive, "synthetic-folder")
            self.assertEqual(session.post.call_args.kwargs["json"]["parents"], ["synthetic-folder"])
            session.post.return_value.headers["Location"] = "https://evil.example/upload/drive/"
            session.put.reset_mock()
            with self.assertRaises(ValueError):
                upload_archive(session, archive, "synthetic-folder")
            session.put.assert_not_called()

    def test_folder_url_validation(self):
        self.assertEqual(folder_id("https://drive.google.com/drive/u/0/folders/synthetic_folder_id"), "synthetic_folder_id")
        with self.assertRaises(ValueError):
            folder_id("https://example.com/drive/folders/synthetic_folder_id")


if __name__ == "__main__":
    unittest.main()
