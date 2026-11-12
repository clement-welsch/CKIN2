import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cloud_inventory import publish, restore


class CloudInventoryTests(unittest.TestCase):
    def test_round_trip_and_versions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "home"
            data = root / "data/processed"
            data.mkdir(parents=True)
            (data / "skins_inventory.csv").write_text("item_name,quantity\nTest,2\n")
            (data / "forecast_archive").mkdir()
            (data / "forecast_archive/run.csv").write_text("forecast\n42\n")
            (data / "secret.json").write_text("excluded")
            folder = Path(temporary) / "cloud"
            first = publish(root, folder)
            original = first.read_bytes()
            (data / "skins_inventory.csv").write_text("item_name,quantity\nTest,3\n")
            second = publish(root, folder)
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_bytes(), original)
            destination = Path(temporary) / "school"
            restore(second, destination)
            for source in data.rglob("*.csv"):
                self.assertEqual(source.read_bytes(), (destination / source.relative_to(root)).read_bytes())
            self.assertFalse((destination / "data/processed/secret.json").exists())
            self.assertTrue((destination / "cloud_manifest.json").exists())
            with self.assertRaises(ValueError):
                restore(first, destination)
            self.assertIn("Test,3", (destination / "data/processed/skins_inventory.csv").read_text())

    def test_reject_unsafe_or_corrupt_archives_without_destination(self):
        for name, digest in [("data/processed/../../outside.csv", hashlib.sha256(b"test").hexdigest()),
                             ("data/processed/inventory.csv", "incorrect")]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                archive = Path(temporary) / "bad.zip"
                with zipfile.ZipFile(archive, "w") as bundle:
                    bundle.writestr(name, b"test")
                    bundle.writestr("manifest.json", json.dumps({"version": 1, "files": {name: digest}}))
                destination = Path(temporary) / "school"
                with self.assertRaises(ValueError):
                    restore(archive, destination)
                self.assertFalse(destination.exists())

    def test_empty_source_and_nested_cloud_folder_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                publish(root, root / "cloud")
            with self.assertRaises(ValueError):
                publish(root, root / "data/processed/cloud")


if __name__ == "__main__":
    unittest.main()
