import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from portfolio_data import CATEGORIES, HOLDINGS, identity, load_holdings
from steam_inventory import apply, parse_export, preview, restore


def export_fixture():
    return dict(schema=1, account_id="synthetic", collected_at="2026-11-01", complete=True, pages=[dict(
        success=1, more_items=0,
        assets=[dict(appid=730, contextid="2", assetid="1", classid="10", instanceid="0", amount="2")],
        descriptions=[dict(appid=730, classid="10", instanceid="0", market_hash_name="Exact Case")])])


def catalog_fixture():
    return pd.DataFrame([dict(item_id=identity("case", "Example"), category="case", item_name="Example", market_hash_name="Exact Case")])


class SteamInventoryImportTests(unittest.TestCase):
    def test_preview_apply_repeat_and_restore_preserve_csvs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "data/processed"
            directory.mkdir(parents=True)
            path = directory / "drop_cases_inventory.csv"
            path.write_text("case_name,quantity\nExample,5\n", encoding="utf-8")
            original = path.read_bytes()
            export, catalog = export_fixture(), catalog_fixture()
            plan = preview(export, catalog, root)
            self.assertEqual(plan["changes"][0]["delta"], -3)
            self.assertFalse((root / "data/imports").exists())
            result = apply(export, catalog, plan["review_token"], root, "home")
            self.assertEqual(load_holdings(root)[0].quantity.tolist(), [2])
            self.assertEqual(load_holdings(root)[1], set(CATEGORIES))
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(result, apply(export, catalog, plan["review_token"], root, "home"))
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()})
            restore(root, "home")
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(load_holdings(root)[0].quantity.tolist(), [5])

    def test_duplicates_pagination_empty_and_invalid_exports(self):
        export = export_fixture()
        page = export["pages"][0]
        page["assets"] *= 2
        self.assertEqual(parse_export(export).quantity.sum(), 2)
        page["more_items"], page["last_assetid"] = 1, "1"
        second = copy.deepcopy(page)
        second.update(start_assetid="1", more_items=0)
        export["pages"].append(second)
        self.assertEqual(parse_export(export).quantity.sum(), 2)
        for mutate in [lambda e: e.update(complete=False),
                       lambda e: e["pages"][1].update(start_assetid="wrong"),
                       lambda e: e["pages"][0].update(success=0)]:
            broken = copy.deepcopy(export)
            mutate(broken)
            with self.assertRaises(ValueError):
                parse_export(broken)
        empty = export_fixture()
        empty["pages"][0].update(assets=[], descriptions=[])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = preview(empty, catalog_fixture(), root)
            apply(empty, catalog_fixture(), plan["review_token"], root, "home")
            self.assertTrue(load_holdings(root)[0].empty)
            self.assertEqual(load_holdings(root)[1], set(CATEGORIES))

    def test_stale_unknown_school_and_atomic_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            export, catalog = export_fixture(), catalog_fixture()
            plan = preview(export, catalog, root)
            with self.assertRaises(ValueError):
                apply(export, catalog, plan["review_token"], root)
            with self.assertRaises(ValueError):
                apply(export, catalog, "stale", root, "home")
            unknown = copy.deepcopy(export)
            unknown["pages"][0]["descriptions"][0]["market_hash_name"] = "Unmatched"
            unresolved = preview(unknown, catalog, root)
            self.assertEqual(unresolved["unresolved"], ["Unmatched"])
            with self.assertRaises(ValueError):
                apply(unknown, catalog, unresolved["review_token"], root, "home")
            with patch("steam_inventory.os.replace", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    apply(export, catalog, plan["review_token"], root, "home")
            self.assertFalse((root / "data/processed/steam_inventory_override.json").exists())
