import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
import plotly.basedatatypes as plots

from test_multicategory_prices import fixture
from portfolio_data import PRICES
from global_snapshots import build_snapshot, save_snapshot
from global_analysis import analyze, explain_changes, market_indices


def market_fixture(holdings, months=3):
    return pd.DataFrame([dict(date=stamp, item_id=row.item_id, category=row.category, item_name=row.item_name,
                              unit_price=(index+1)*10, source="steam", currency="EUR", date_estimated=False)
                         for index, stamp in enumerate(pd.date_range("2023-01-31", periods=months, freq="ME"))
                         for row in holdings.itertuples()], columns=PRICES)


def run_notebook(name, data_root):
    """Execute every authored cell with real Plotly serialization and no CSV writes."""
    root = Path(__file__).resolve().parents[1]
    notebook = json.loads((root / "notebook" / name).read_text(encoding="utf-8"))
    before = {p: p.read_bytes() for p in data_root.rglob("*.csv")}
    figures = []
    def show(figure, *args, **kwargs):
        figures.append(json.loads(figure.to_json()))
    scope = {"__name__": "__main__"}
    old = Path.cwd()
    try:
        os.chdir(root)
        with patch.dict(os.environ, {"CKIN2_DATA_ROOT": str(data_root)}), patch.object(plots.BaseFigure, "show", show), contextlib.redirect_stdout(io.StringIO()):
            for index, cell in enumerate(notebook["cells"]):
                if cell["cell_type"] == "code":
                    if cell.get("outputs") or cell.get("execution_count") is not None:
                        raise AssertionError("Published notebook contains execution outputs")
                    exec(compile("".join(cell["source"]), f"{name}:cell{index}", "exec"), scope)
    finally:
        os.chdir(old)
    after = {p: p.read_bytes() for p in data_root.rglob("*.csv")}
    if before != after:
        raise AssertionError("Notebook changed CSV data")
    return scope, figures


class GlobalAnalysisTests(unittest.TestCase):
    def test_common_base_fixed_weights_and_stale_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            holdings, _ = fixture(Path(directory))
            prices = market_fixture(holdings)
            indices, diagnostic = market_indices(holdings, prices)
            self.assertEqual(diagnostic["reason"], "")
            self.assertEqual(indices.loc[indices.category.eq("global"), "index_100"].tolist(), [100, 200, 300])
            # One stale item must make the global index unavailable, not change the cohort.
            prices = prices.loc[~(prices.item_id.eq(holdings.iloc[0].item_id) & prices.date.gt("2023-01-31"))]
            indices, _ = market_indices(holdings, prices, max_age_days=10)
            self.assertTrue(pd.isna(indices.loc[indices.category.eq("global"), "index_100"].iloc[-1]))

    def test_estimated_dates_zero_bases_and_no_common_date(self):
        with tempfile.TemporaryDirectory() as directory:
            holdings, _ = fixture(Path(directory))
            prices = market_fixture(holdings, 1)
            prices.loc[0, "unit_price"] = 0
            indices, diagnostic = market_indices(holdings, prices)
            self.assertTrue(indices.empty)
            self.assertIn("Zero", diagnostic["reason"])
            prices.loc[0, "date_estimated"] = True
            indices, diagnostic = market_indices(holdings, prices)
            self.assertTrue(indices.empty)
            self.assertIn("common", diagnostic["reason"])

    def test_price_and_quantity_decomposition_reconciles(self):
        with tempfile.TemporaryDirectory() as directory:
            holdings, imported = fixture(Path(directory))
            first = build_snapshot(holdings, imported, "2023-01-31")
            later = holdings.copy()
            later.loc[0, "quantity"] = 4
            last = build_snapshot(later, imported, "2023-02-28")
            changes = explain_changes(pd.concat([first, last]), market_fixture(holdings))
            self.assertTrue(changes.covered.all())
            self.assertEqual(changes.value_change.sum(), 110)
            self.assertEqual(changes.price_effect.sum() + changes.quantity_effect.sum(), 110)

    def test_full_notebook_on_complete_partial_and_empty_data(self):
        for scenario in ["complete", "partial", "empty"]:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                if scenario != "empty":
                    holdings, imported = fixture(root)
                    market_fixture(holdings).to_csv(root / "data/processed/market_observations.csv", index=False)
                    path = root / "data/processed/global_inventory_history.csv"
                    save_snapshot(holdings, imported, "2023-01-31", path)
                    save_snapshot(holdings, imported, "2023-02-28", path)
                    if scenario == "partial":
                        (root / "data/processed/skins_inventory.csv").unlink()
                scope, figures = run_notebook("global_book.ipynb", root)
                if scenario == "complete":
                    self.assertEqual(len(figures), 4)
                    self.assertEqual(scope["result"]["current"].loc[lambda f: f.category.eq("global"), "total_value"].iloc[0], 210)
                if scenario == "empty":
                    self.assertEqual(figures, [])


if __name__ == "__main__":
    unittest.main()
