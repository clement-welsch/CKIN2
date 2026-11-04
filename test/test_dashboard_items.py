from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dashboard import render, view
from dashboard_items import item_details
from market_universe import publish
from portfolio_data import PRICES, identity
from global_snapshots import build_snapshot
from test_market_universe import release_fixture
from test_multicategory_prices import fixture
from test_global_analysis import market_fixture


class DashboardItemTests(unittest.TestCase):
    def test_owned_details_use_shared_value_and_explicit_purchase_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            holdings, _ = fixture(root)
            prices = market_fixture(holdings)
            prices.to_csv(root / "data/processed/market_observations.csv", index=False)
            path = root / "data/processed/skins_inventory.csv"
            inventory = pd.read_csv(path)
            inventory["purchase_unit_price"], inventory["purchase_date"] = 4, "2022-01-01"
            inventory.to_csv(path, index=False)
            item = holdings.loc[holdings.category.eq("skin"), "item_id"].iloc[0]
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            data = view(root, item_id=item, components="item", now="2023-04-01")
            detail = item_details(root, data, item)
            self.assertTrue(detail["held"])
            self.assertEqual(detail["valuation"].market_value.iloc[0], 30)
            self.assertEqual(detail["purchase_metadata"]["purchase_unit_price"], 4)
            self.assertTrue(detail["gains"].empty)  # CSV price is not an invented FIFO gain.
            page = render(root, {"page": "item", "item_id": item}, now="2023-04-01")
            self.assertIn("Redline", page)
            self.assertIn("ByMykel", page)
            self.assertIn("médiane historique", page)
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()})
            # A confirmed opening lot cost, not the CSV display price, drives FIFO.
            build_snapshot(holdings, set(holdings.category), "2023-01-01").to_csv(root / "data/processed/opening_inventory.csv", index=False)
            pd.DataFrame([dict(item_id=item, total_cost=5)]).to_csv(root / "data/processed/opening_costs.csv", index=False)
            confirmed = view(root, item_id=item, components="item", now="2023-04-01")
            gains = item_details(root, confirmed, item)["gains"]
            self.assertEqual(gains.remaining_cost.iloc[0], 5)
            self.assertEqual(gains.unrealized_gain.iloc[0], 25)

    def test_non_owned_release_variants_future_and_missing_prices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release = release_fixture()
            first = dict(item_id=identity("skin", "Example (Factory New)"), category="skin", item_name="Example (Factory New)",
                         market_hash_name="Example (Factory New)", source_id="variant-1", wear="Factory New", variant="normal", collection="Example Collection")
            second = dict(first, item_id=identity("skin", "StatTrak™ Example (Factory New)"), item_name="StatTrak™ Example (Factory New)",
                          market_hash_name="StatTrak™ Example (Factory New)", source_id="variant-2", variant="stattrak")
            release["items"] = [first, second]
            publish(release, root, "home")
            data = view(root, components="item", now="2026-01-03")
            self.assertEqual(len(data["registry"]), 2)
            detail = item_details(root, data, first["item_id"])
            self.assertFalse(detail["held"])
            self.assertTrue(detail["valuation"].empty)
            self.assertTrue(pd.isna(detail["latest_price"]))
            self.assertEqual(detail["item"]["variant"], "normal")
            self.assertEqual(detail["item"]["collection"], "Example Collection")
            self.assertEqual(len(view(root, components="item", now="2026-01-01")["registry"]), 0)
            page = render(root, {"page": "item", "search": "StatTrak"}, now="2026-01-03")
            self.assertIn("StatTrak", page)
            self.assertNotIn('>Example (Factory New) ·', page)
            with self.assertRaises(ValueError):
                view(root, category="case", item_id=first["item_id"], now="2026-01-03")

    def test_independent_prices_gaps_zero_base_and_acquisition_exclusion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            holdings, _ = fixture(root)
            item = holdings.loc[holdings.category.eq("skin")].iloc[0]
            path = root / "data/market"
            path.mkdir(parents=True)
            rows = [dict(date=date, item_id=item.item_id, category="skin", item_name=item.item_name, unit_price=price,
                         currency="EUR", source="steam", date_estimated=False) for date, price in
                    [("2023-01-01", 0), ("2023-02-01", float("nan")), ("2023-03-01", 10), ("2024-01-01", 999)]]
            pd.DataFrame(rows, columns=PRICES).to_csv(path / "observations.csv", index=False)
            pd.DataFrame([dict(date="2022-01-01", item_name=item.item_name, unit_price=7, source_column=0,
                               date_estimated=False)]).to_csv(root / "data/processed/skins_prices.csv", index=False)
            data = view(root, item_id=item.item_id, components="item", now="2023-04-01")
            detail = item_details(root, data, item.item_id)
            self.assertEqual(detail["latest_price"], 10)
            self.assertEqual(detail["valuation"].market_value.iloc[0], 10)
            self.assertEqual(len(detail["prices"]), 3)
            self.assertTrue(detail["prices"].index_100.isna().all())
            self.assertTrue(pd.isna(detail["prices"].unit_price.iloc[1]))
            self.assertEqual(detail["acquisitions"].unit_price.tolist(), [7])
            self.assertTrue(pd.isna(detail["purchase_metadata"]["purchase_unit_price"]))
            self.assertEqual(detail["observations"], 2)
