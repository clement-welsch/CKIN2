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
    def test_account_breakdown_preserves_empty_unknown_and_duplicate_assets(self):
        first, second, empty = export_fixture(), export_fixture(), export_fixture()
        second['account_id'] = 'unknown'
        second['pages'][0]['descriptions'][0]['market_hash_name'] = 'Unknown listing'
        first['pages'][0]['assets'] *= 2
        empty['account_id'] = 'empty'
        empty['pages'][0].update(assets=[], descriptions=[])
        with tempfile.TemporaryDirectory() as directory:
            bundle = dict(schema=2, complete=True, accounts=[first, second, empty])
            result = preview(bundle, catalog_fixture(), Path(directory))
            accounts = {row['account_id']: row for row in result['accounts']}
            self.assertEqual(accounts['synthetic']['asset_count'], 1)
            self.assertEqual(accounts['synthetic']['matched_quantity'], 2)
            self.assertEqual(accounts['unknown']['unresolved_quantity'], 2)
            self.assertEqual(accounts['unknown']['unresolved'], ['Unknown listing'])
            self.assertEqual(accounts['empty']['total_quantity'], 0)
            self.assertEqual(accounts['empty']['holdings'], [])
            self.assertEqual(sum(row['matched_quantity'] for row in accounts.values()),
                             sum(row['quantity'] for row in result['holdings']))
            self.assertFalse(list(Path(directory).rglob('*')))

    def test_missing_identity_fields_cannot_match_each_other_or_modify_inventory(self):
        for field in ("classid", "instanceid"):
            for invalid in (None, "", "None", "²", 10):
                with self.subTest(field=field, invalid=invalid), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    export = export_fixture()
                    page = export["pages"][0]
                    page["assets"][0][field] = invalid
                    page["descriptions"][0][field] = invalid
                    with self.assertRaises(ValueError):
                        preview(export, catalog_fixture(), root)
                    self.assertFalse(list(root.rglob("*")))

    def test_repeated_cursors_and_malformed_pages_are_rejected(self):
        export = export_fixture()
        first = export["pages"][0]
        first.update(more_items=1, last_assetid="1")
        middle = copy.deepcopy(first)
        middle["start_assetid"] = "1"
        final = copy.deepcopy(middle)
        final["more_items"] = 0
        export["pages"].extend([middle, final])
        with self.assertRaisesRegex(ValueError, "Repeated"):
            parse_export(export)
        for page in (None, [], dict(success=True), dict(success=0)):
            broken = export_fixture()
            broken["pages"] = [page]
            with self.assertRaises(ValueError):
                parse_export(broken)

    def test_multi_account_preview_scopes_assets_and_rejects_partial_or_changed_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = export_fixture(), export_fixture()
            second.update(account_id="second", collected_at="2026-11-02")
            second["pages"][0]["assets"][0]["amount"] = "3"
            bundle = dict(schema=2, complete=True, accounts=[first, second])
            plan = preview(bundle, catalog_fixture(), root)
            self.assertEqual(plan["holdings"][0]["quantity"], 5)
            self.assertEqual({a["account_id"] for a in plan["assets"]}, {"synthetic", "second"})
            self.assertEqual(plan["account_collected_at"], {"synthetic": "2026-11-01", "second": "2026-11-02"})
            self.assertFalse(list(root.rglob("*")))
            with self.assertRaisesRegex(ValueError, "school"):
                apply(bundle, catalog_fixture(), plan["review_token"], root)
            result = apply(bundle, catalog_fixture(), plan["review_token"], root, "home")
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(result, apply(bundle, catalog_fixture(), plan["review_token"], root, "home"))
            single = preview(first, catalog_fixture(), root)
            with self.assertRaisesRegex(ValueError, "account selection"):
                apply(first, catalog_fixture(), single["review_token"], root, "home")
            stale = copy.deepcopy(bundle)
            stale["accounts"][0]["collected_at"] = "2026-10-01"
            stale["accounts"][1]["collected_at"] = "2026-11-03"
            stale_plan = preview(stale, catalog_fixture(), root)
            with self.assertRaisesRegex(ValueError, "older"):
                apply(stale, catalog_fixture(), stale_plan["review_token"], root, "home")
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()})
            restore(root, "home")
            self.assertFalse((root / "data/processed/steam_inventory_override.json").exists())
            duplicate = dict(schema=2, complete=True, accounts=[first, first])
            with self.assertRaisesRegex(ValueError, "Duplicate account"):
                preview(duplicate, catalog_fixture(), root)
            second["complete"] = False
            with self.assertRaises(ValueError):
                preview(bundle, catalog_fixture(), root)

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
