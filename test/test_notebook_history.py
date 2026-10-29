"""Run notebook analyses on synthetic histories without displaying charts."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from analyze_drop_cases import prepare_inventory, prepare_price_history


class NotebookHistoryTests(unittest.TestCase):
    def run_analyses(self, rows, snapshots=None):
        raw = pd.DataFrame(rows, columns=["date", "case_name", "unit_price"])
        prices = prepare_price_history(raw)
        missing = int(prices.unit_price.isna().sum())
        prices = prices.dropna(subset=["unit_price"]).sort_values(["case_name", "date"])
        scope = {
            "pd": pd, "np": np, "sys": sys, "PROJECT_ROOT": PROJECT_ROOT,
            "prices": prices, "invalid_price_rows": missing,
            "inventory": pd.DataFrame({"case_name": ["Alpha", "Beta"], "quantity": [2, 1]}),
            "snapshots": prepare_inventory(pd.DataFrame({
                "snapshot_date": ["2026-02-01", "2026-02-01"],
                "case_name": ["Alpha", "Beta"], "quantity": [2, 1],
            }), historical=True),
            "display": Mock(), "px": Mock(), "go": Mock(),
        }
        notebook = json.loads((PROJECT_ROOT / "notebook/cases_book.ipynb").read_text(encoding="utf-8"))
        if snapshots is not None:
            scope["snapshots"] = prepare_inventory(snapshots, historical=True)
        with redirect_stdout(StringIO()) as output:
            for index, cell in enumerate(notebook["cells"]):
                if cell["cell_type"] == "code" and index > 2:
                    exec(compile("".join(cell["source"]), f"cell_{index}", "exec"), scope)
        return scope, output.getvalue()

    def test_no_common_date_keeps_micro_and_portfolio_analyses(self):
        scope, output = self.run_analyses([
            ("2026-01-01", "Alpha", 4.0), ("2026-01-02", "Beta", 3.0),
        ])
        self.assertTrue(scope["macro_index"].empty)
        self.assertIsNone(scope["macro_base_date"])
        self.assertIn("aucune date commune", output)
        scope["go"].Figure.assert_not_called()
        self.assertEqual(len(scope["case_summary"]), 2)
        self.assertEqual(scope["known_value"], 11.0)
        self.assertEqual(scope["portfolio_history"].total_value.tolist(), [11.0])
        self.assertIn("Meilleure évolution", output)

    def test_empty_or_all_missing_prices_keep_unavailable_portfolio(self):
        for rows in ([], [("2026-01-01", "Alpha", None)]):
            with self.subTest(rows=rows):
                scope, output = self.run_analyses(rows)
                self.assertTrue(scope["macro_index"].empty)
                self.assertTrue(scope["case_summary"].empty)
                self.assertIn("aucun relevé de prix valide", output)
                self.assertTrue(scope["current_value"].market_value.isna().all())
                self.assertEqual(scope["portfolio_history"].cases_without_price.tolist(), [2])
                scope["go"].Figure.assert_not_called()

    def test_complete_dates_preserve_fixed_cohort_and_exclude_partial_dates(self):
        scope, output = self.run_analyses([
            ("2026-01-01", "Alpha", 4.0), ("2026-01-01", "Beta", 2.0),
            ("2026-01-02", "Alpha", 8.0),
            ("2026-01-03", "Alpha", 8.0), ("2026-01-03", "Beta", 3.0),
        ])
        self.assertEqual(scope["macro_base_date"], pd.Timestamp("2026-01-01"))
        self.assertEqual(scope["macro_index"].equal_weight_index.tolist(), [100.0, 175.0])
        self.assertEqual(scope["macro_index"].cases_observed.tolist(), [2, 2])
        scope["go"].Figure.assert_called_once()
        self.assertNotIn("Indice macro indisponible", output)

    def test_zero_bases_are_unavailable_without_losing_valuation(self):
        for values in ([0.0, 0.0], [0.0, 4.0]):
            with self.subTest(values=values):
                scope, output = self.run_analyses([
                    ("2026-01-01", "Alpha", values[0]),
                    ("2026-01-02", "Alpha", values[1]),
                    ("2026-01-01", "Beta", 2.0),
                    ("2026-01-02", "Beta", 3.0),
                ])
                alpha = scope["case_summary"].set_index("case_name").loc["Alpha"]
                self.assertTrue(pd.isna(alpha.change_pct_since_first))
                self.assertTrue(pd.isna(alpha.observed_range_pct))
                if values[-1] == 0:
                    self.assertTrue(pd.isna(alpha.drawdown_from_peak_pct))
                else:
                    self.assertEqual(alpha.drawdown_from_peak_pct, 0.0)
                self.assertTrue(scope["macro_index"].empty)
                self.assertTrue(scope["prices"].loc[scope["prices"].case_name.eq("Alpha"), "index_100"].isna().all())
                self.assertIn("base nulle", output)
                self.assertNotIn("inf%", output)
                self.assertNotIn("nan%", output)
                for name in ("prices", "case_summary", "portfolio_history", "current_value"):
                    self.assertFalse(np.isinf(scope[name].select_dtypes(include="number").to_numpy(dtype=float)).any())
                self.assertEqual(scope["known_value"], values[-1] * 2 + 3.0)

    def test_all_zero_history_and_zero_snapshot_base_have_no_infinities(self):
        scope, output = self.run_analyses([
            ("2026-01-01", "Alpha", 0.0), ("2026-01-02", "Alpha", 0.0),
            ("2026-01-01", "Beta", 0.0), ("2026-01-02", "Beta", 0.0),
        ])
        self.assertEqual(scope["known_value"], 0.0)
        self.assertEqual(scope["portfolio_history"].total_value.tolist(), [0.0])
        self.assertTrue(scope["case_summary"].change_pct_since_first.isna().all())
        self.assertIn("indisponible", output)
        self.assertNotIn("nan%", output)

    def test_snapshot_change_from_zero_is_unavailable(self):
        snapshots = pd.DataFrame({
            "snapshot_date": ["2026-01-01", "2026-01-02"],
            "case_name": ["Alpha", "Alpha"], "quantity": [1, 1],
        })
        scope, output = self.run_analyses([
            ("2026-01-01", "Alpha", 0.0), ("2026-01-02", "Alpha", 4.0),
        ], snapshots=snapshots)
        self.assertEqual(scope["portfolio_history"].total_value.tolist(), [0.0, 4.0])
        self.assertTrue(scope["portfolio_history"].change_pct.isna().all())
        self.assertIn("snapshot précédent nulle", output)

    def test_positive_base_can_fall_to_zero(self):
        scope, _ = self.run_analyses([
            ("2026-01-01", "Alpha", 4.0), ("2026-01-02", "Alpha", 0.0),
        ])
        self.assertEqual(scope["prices"].index_100.tolist(), [100.0, 0.0])
        self.assertEqual(scope["case_summary"].change_pct_since_first.tolist(), [-100.0])


if __name__ == "__main__":
    unittest.main()
