import copy
import json
from pathlib import Path
import tempfile
import unittest
import sys
import subprocess
from unittest.mock import Mock

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from market_universe import collect, compare_releases, indices, load_release, publish, validate_release
from portfolio_data import CATEGORIES, identity


def release_fixture():
    return dict(schema=1, source_url="https://example.test/catalog", source_revision="revision-1",
                scope="synthetic six-category selection", source_updated_at="2026-01-01", collected_at="2026-01-02",
                items=[dict(item_id=identity(c, c), category=c, item_name=c, market_hash_name=c + " exact listing",
                            source_id=c, wear=None, variant="souvenir" if c == "souvenir" else "normal", collection=None)
                       for c in CATEGORIES])


class MarketUniverseTests(unittest.TestCase):
    def test_release_comparison_keeps_source_continuity_without_migrating_prices(self):
        original = release_fixture()
        changed = copy.deepcopy(original)
        changed.update(source_revision="revision-2", collected_at="2026-02-01")
        renamed = changed["items"][0]
        renamed.update(item_name="renamed case", item_id=identity(renamed["category"], "renamed case"),
                       market_hash_name="renamed exact listing")
        removed = changed["items"].pop()
        added = dict(removed, source_id="new-source-variant", item_name="new item",
                     item_id=identity(removed["category"], "new item"), market_hash_name="new exact listing")
        changed["items"].append(added)
        changed["items"][1]["collection"] = "reviewed collection"
        before = copy.deepcopy((original, changed))
        result = compare_releases(original, changed)
        self.assertEqual(result["counts"]["renamed"], 1)
        self.assertEqual(result["counts"]["removed_from_selection"], 1)
        self.assertEqual(result["counts"]["added"], 1)
        self.assertEqual(result["counts"]["metadata_changed"], 1)
        self.assertEqual(before, (original, changed))
        # Item order cannot change a source-ID comparison.
        changed["items"].reverse()
        self.assertEqual(result["changes"], compare_releases(original, changed)["changes"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_key = publish(original, root, "home")
            new_key = publish(changed, root, "home")
            old_id = original["items"][0]["item_id"]
            collect(root, old_key, [old_id], environment="home", now="2026-01-03", fetch=lambda _: 2)
            snapshot = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            old, _ = load_release(root, old_key, "2026-03-01")
            new, _ = load_release(root, new_key, "2026-03-01")
            compare_releases(old, new)
            command = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "src/market_universe.py"),
                                      "school", "--root", str(root), "--compare", old_key, new_key],
                                     check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(command.stdout)["counts"]["renamed"], 1)
            self.assertEqual(snapshot, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()})
            self.assertEqual(pd.read_csv(root / "data/market/observations.csv").item_id.tolist(), [old_id])

    def test_comparison_rejects_future_reverse_sources_and_duplicate_ids(self):
        original = release_fixture()
        changed = copy.deepcopy(original)
        changed["source_url"] = "https://other.example/catalog"
        with self.assertRaisesRegex(ValueError, "different sources"):
            compare_releases(original, changed)
        changed = copy.deepcopy(original)
        changed.update(source_updated_at="2025-01-01", collected_at="2025-01-02")
        with self.assertRaisesRegex(ValueError, "predates"):
            compare_releases(original, changed)
        changed = copy.deepcopy(original)
        changed["items"][1]["source_id"] = changed["items"][0]["source_id"]
        with self.assertRaises(ValueError):
            compare_releases(original, changed)
        changed = copy.deepcopy(original)
        changed["items"][0]["wear"] = "reviewed wear"
        self.assertEqual(compare_releases(original, changed)["counts"]["identity_metadata_changed"], 1)

    def test_all_categories_without_inventory_budget_partial_and_idempotence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release = release_fixture()
            key = publish(release, root, "home")
            watch = [r["item_id"] for r in release["items"]]
            fetch = Mock(side_effect=[1, None, 0])
            report = collect(root, key, watch, environment="home", now="2026-01-03", budget=3, fetch=fetch, pause=lambda _: None)
            self.assertEqual(fetch.call_count, 3)
            self.assertEqual(report.outcome.tolist(), ["updated", "unavailable", "updated", *["not_requested"]*3])
            target = root / "data/market/observations.csv"
            collect(root, key, watch[:1], environment="home", now="2026-01-03", budget=1, fetch=lambda _: 2)
            self.assertEqual(len(pd.read_csv(target)), 2)
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            report = collect(root, key, watch, now="2026-01-04", fetch=Mock(side_effect=AssertionError("network")))
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()})
            self.assertFalse((root / "data/processed").exists())
            self.assertEqual(report.unit_price.notna().sum(), 2)

    def test_release_versions_future_membership_and_index_cohort(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            release = release_fixture()
            key = publish(release, root, "home")
            self.assertEqual(key, publish(release, root, "home"))
            with self.assertRaises(ValueError):
                load_release(root, key, "2026-01-01")
            watch = [release["items"][0]["item_id"]]
            for date, price in [("2026-01-03", 2), ("2026-02-03", 4)]:
                collect(root, key, watch, environment="home", now=date, fetch=lambda _: price)
            frame, diagnostic = indices(root, key, watch, "2026-02-03")
            self.assertEqual(frame.loc[frame.category.eq("global"), "index_100"].tolist(), [100, 200])
            self.assertEqual(diagnostic["release_id"], key)
            changed = copy.deepcopy(release)
            changed["items"].pop()
            changed["source_revision"] = "revision-2"
            self.assertNotEqual(publish(changed, root, "home"), key)
            self.assertEqual(len(load_release(root, key, "2026-03-01")[1]), 6)

    def test_invalid_listings_watchlist_and_failures(self):
        release = release_fixture()
        release["items"][1]["market_hash_name"] = release["items"][0]["market_hash_name"]
        with self.assertRaises(ValueError):
            validate_release(release)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            key = publish(release_fixture(), root, "home")
            with self.assertRaises(ValueError):
                collect(root, key, ["unknown"], now="2026-02-01")
            watch = [release_fixture()["items"][0]["item_id"]]
            result = collect(root, key, watch, environment="home", now="2026-02-01", fetch=Mock(side_effect=TimeoutError))
            self.assertEqual(result.outcome.iloc[0], "unavailable")
            self.assertFalse((root / "data/market/observations.csv").exists())
