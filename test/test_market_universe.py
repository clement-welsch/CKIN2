import copy
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import Mock

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from market_universe import collect, indices, load_release, publish, validate_release
from portfolio_data import CATEGORIES, identity


def release_fixture():
    return dict(schema=1, source_url="https://example.test/catalog", source_revision="revision-1",
                scope="synthetic six-category selection", source_updated_at="2026-01-01", collected_at="2026-01-02",
                items=[dict(item_id=identity(c, c), category=c, item_name=c, market_hash_name=c + " exact listing",
                            source_id=c, wear=None, variant="souvenir" if c == "souvenir" else "normal", collection=None)
                       for c in CATEGORIES])


class MarketUniverseTests(unittest.TestCase):
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
