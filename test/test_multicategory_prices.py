import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from portfolio_data import CATEGORIES, HOLDINGS, PRICES, identity, load_holdings, load_prices
from update_market_prices import catalog_template, collect, validate_catalog


def fixture(root):
    target = root / "data/processed"
    target.mkdir(parents=True)
    pd.DataFrame({"case_name": ["Recoil"], "quantity": [2]}).to_csv(target / "drop_cases_inventory.csv", index=False)
    for prefix, names, kinds in [("skins", ["AK-47 | Redline (Field-Tested)"], ["skin"]),
                                ("souvenirs", ["Test Souvenir Package"], ["souvenir"]),
                                ("others", ["Sticker | Test", "Charm | Test", "Agent | Test"], ["sticker", "charm", "agent"])]:
        pd.DataFrame({"item_name": names, "item_type": kinds, "quantity": [1] * len(names)}).to_csv(target / f"{prefix}_inventory.csv", index=False)
    holdings, imported = load_holdings(root)
    catalog = catalog_template(holdings)
    catalog.loc[catalog.category.ne("case"), "market_hash_name"] = catalog.loc[catalog.category.ne("case"), "item_name"]
    catalog.to_csv(target / "market_catalog.csv", index=False)
    return holdings, imported


class MarketTests(unittest.TestCase):
    def test_all_categories_exact_names_metadata_and_idempotence(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            holdings, imported = fixture(root)
            self.assertEqual(imported, set(CATEGORIES))
            names = []
            def fetch(name):
                names.append(name)
                return 2.5
            collect(root, "home", now="2026-01-01", fetch=fetch, pause=lambda _: None)
            self.assertIn("Recoil Case", names)
            self.assertIn("AK-47 | Redline (Field-Tested)", names)
            path = root / "data/processed/market_observations.csv"
            before = path.read_bytes()
            collect(root, "home", now="2026-01-01", fetch=lambda _: 2.5, pause=lambda _: None)
            self.assertEqual(before, path.read_bytes())
            prices = load_prices(root)
            self.assertEqual(len(prices), 6)
            self.assertTrue(prices.currency.eq("EUR").all())
            self.assertTrue(prices.source.eq("steam").all())
            self.assertFalse(prices.date_estimated.any())

    def test_failed_collection_and_school_are_read_only(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            fixture(root)
            collect(root, "home", now="2026-01-01", fetch=lambda _: 3, pause=lambda _: None)
            path = root / "data/processed/market_observations.csv"
            before = path.read_bytes()
            report = collect(root, "home", now="2026-02-01", fetch=lambda _: None, pause=lambda _: None)
            self.assertTrue(report.outcome.eq("failed").all())
            self.assertTrue(report.unit_price.eq(3).all())
            self.assertEqual(before, path.read_bytes())
            with patch("update_market_prices.fetch_market_price", side_effect=AssertionError("network")):
                collect(root, "school", now="2026-02-01")
            self.assertEqual(before, path.read_bytes())

    def test_catalog_requires_review_and_rejects_duplicate_listing(self):
        with tempfile.TemporaryDirectory() as directory:
            holdings, _ = fixture(Path(directory))
            template = catalog_template(holdings)
            with self.assertRaises(ValueError):
                validate_catalog(template, holdings)
            template.market_hash_name = "same"
            with self.assertRaises(ValueError):
                validate_catalog(template, holdings)

    def test_legacy_prices_acquisition_exclusion_and_immutable_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            holdings, _ = fixture(root)
            path = root / "data/processed/skins_prices.csv"
            pd.DataFrame({"date": ["2026-01-01"] * 2, "item_name": [holdings.loc[holdings.category.eq('skin'), 'item_name'].iloc[0]] * 2,
                          "unit_price": [100, 9], "source_column": [0.0, 2.0], "date_estimated": [False, False]}).to_csv(path, index=False)
            before = path.read_bytes()
            prices = load_prices(root)
            self.assertEqual(prices.unit_price.tolist(), [9])
            self.assertEqual(before, path.read_bytes())

    def test_catalog_preserves_historical_other_item_classification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            holdings, _ = fixture(root)
            target = root / "data/processed"
            agent = holdings.loc[holdings.category.eq("agent")].iloc[0]
            pd.DataFrame({"date": ["2026-01-01"], "item_name": [agent.item_name], "unit_price": [5],
                          "source_column": [2], "date_estimated": [False]}).to_csv(target / "others_prices.csv", index=False)
            current = pd.read_csv(target / "others_inventory.csv")
            current.loc[current.item_type.ne("agent")].to_csv(target / "others_inventory.csv", index=False)
            remaining, _ = load_holdings(root)
            catalog = validate_catalog(pd.read_csv(target / "market_catalog.csv"), remaining)
            self.assertEqual(len(catalog), 5)
            self.assertEqual(load_prices(root).category.tolist(), ["agent"])


if __name__ == "__main__":
    unittest.main()
