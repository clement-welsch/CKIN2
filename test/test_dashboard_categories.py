import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from analyze_categories import analyze_category, prepare_category_prices
from dashboard import render, view
from dashboard_categories import category_data, category_figures
from test_multicategory_prices import fixture
from test_global_analysis import market_fixture


class DashboardCategoryTests(unittest.TestCase):
    def test_notebook_parity_six_categories_and_no_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            holdings, _ = fixture(root)
            prices = market_fixture(holdings)
            prices.to_csv(root / "data/processed/market_observations.csv", index=False)
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            data = view(root, now="2023-04-01", components="categories")
            results = category_data(root, data)
            self.assertEqual({r["category"] for r in results}, set(holdings.category))
            self.assertEqual(sum(len(r["holdings"]) for r in results), len(holdings))
            skin = next(r for r in results if r["category"] == "skin")
            inventory = holdings.loc[holdings.category.eq("skin")].assign(purchase_unit_price=float("nan"))
            notebook = analyze_category(inventory, prices.loc[prices.category.eq("skin")])[0]
            pd.testing.assert_frame_equal(skin["prices"][notebook.columns], notebook)
            with patch("dashboard.experiment", side_effect=AssertionError("irrelevant model call")):
                page = render(root, {"page": "categories", "category": "skin"}, now="2023-04-01")
            self.assertIn('aria-current="page"', page)
            self.assertIn("<h2>Skins</h2>", page)
            self.assertNotIn("<h2>Agents</h2>", page)
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()})

    def test_acquisitions_never_enter_market_and_zero_base_stays_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            holdings, _ = fixture(root)
            skin = holdings.loc[holdings.category.eq("skin")].iloc[0]
            pd.DataFrame([dict(date="2023-01-01", item_name=skin.item_name, unit_price=999, source_column=0, date_estimated=False),
                          dict(date="2023-02-01", item_name=skin.item_name, unit_price=0, source_column=1, date_estimated=False),
                          dict(date="2023-03-01", item_name=skin.item_name, unit_price=10, source_column=2, date_estimated=True)]).to_csv(root / "data/processed/skins_prices.csv", index=False)
            data = view(root, category="skin", now="2023-04-01", components="categories")
            result = category_data(root, data)[0]
            self.assertEqual(result["prices"].unit_price.tolist(), [0, 10])
            self.assertTrue(result["prices"].index_100.isna().all())
            self.assertEqual(result["acquisitions"].unit_price.tolist(), [999])
            self.assertEqual(len(category_figures(result)), 2)
            for page in ("overview", "categories", "item", "performance", "forecasts", "community"):
                self.assertIn("Sources et licences", render(root, {"page": page}, now="2023-04-01"))
            with self.assertRaises(ValueError):
                render(root, {"page": "unknown"})

    def test_explicit_missing_points_remain_plot_gaps(self):
        raw = pd.DataFrame(dict(item_name=["Example"]*4, date=["2023-01-01", "2023-02-01", "2023-03-01", "2023-03-01"],
                                unit_price=[1, float("nan"), 3, float("nan")]))
        series = prepare_category_prices(raw, keep_missing=True)
        self.assertEqual(len(series), 3)
        self.assertTrue(pd.isna(series.unit_price.iloc[1]))
        self.assertEqual(series.unit_price.iloc[-1], 3)
        self.assertEqual(series.index_100.iloc[-1], 300)
