"""Regression tests for complete and partial portfolio valuations."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import analyze_drop_cases
import portfolio_report
from update_drop_cases import Environment
from analyze_drop_cases import (
    calculate_historical_portfolio_value,
    calculate_inventory_value,
    print_inventory_value_summary,
    summarize_inventory_value,
)


class ValuationCoverageTests(unittest.TestCase):
    def setUp(self):
        self.prices = pd.DataFrame({
            "case_name": ["Alpha"], "date": ["2026-01-01"], "unit_price": [4.0],
        })

    def valuation(self, names, quantities):
        return calculate_inventory_value(
            pd.DataFrame({"case_name": names, "quantity": quantities}), self.prices
        )

    def test_current_complete_partial_unpriced_empty_and_zero_quantity(self):
        scenarios = [
            (["Alpha"], [3], 12.0, 12.0, 1, 1),
            (["Alpha", "Beta"], [3, 2], 12.0, None, 1, 2),
            (["Beta"], [2], None, None, 0, 1),
            ([], [], 0.0, 0.0, 0, 0),
            (["Alpha", "Beta"], [3, 0], 12.0, 12.0, 1, 1),
            (["Beta"], [0], 0.0, 0.0, 0, 0),
        ]
        for names, quantities, known, total, priced, held in scenarios:
            with self.subTest(names=names, quantities=quantities):
                summary = summarize_inventory_value(self.valuation(names, quantities))
                for key, expected in (("known_value", known), ("total_value", total)):
                    if expected is None:
                        self.assertTrue(pd.isna(summary[key]))
                    else:
                        self.assertEqual(summary[key], expected)
                self.assertEqual(summary["priced_cases"], priced)
                self.assertEqual(summary["total_cases"], held)
                self.assertEqual(summary["cases_without_price"], held - priced)

    def test_console_labels_partial_and_unavailable_values(self):
        for names, quantities, message in [
            (["Alpha"], [3], "Total inventory value: 12.00 EUR"),
            (["Alpha", "Beta"], [3, 2], "Known inventory value (partial): 12.00 EUR"),
            (["Beta"], [2], "Known inventory value: unavailable (no valid prices)"),
            ([], [], "Total inventory value: 0.00 EUR"),
        ]:
            with self.subTest(names=names), redirect_stdout(StringIO()) as output:
                print_inventory_value_summary(self.valuation(names, quantities))
                text = output.getvalue()
                self.assertIn(message, text)
                self.assertIn("Price coverage:", text)
                if "Beta" in names:
                    self.assertIn("Total inventory value: unavailable", text)
                    self.assertNotIn("Total inventory value: 12.00 EUR", text)

    def test_both_console_entry_points_use_partial_summary(self):
        inventory = pd.DataFrame({"case_name": ["Alpha", "Beta"], "quantity": [3, 2]})
        history = pd.DataFrame(columns=["snapshot_date", "case_name", "quantity"])
        for module in (analyze_drop_cases, portfolio_report):
            def read_csv(path):
                if path == module.INVENTORY_PATH:
                    return inventory.copy()
                if path == module.PRICE_HISTORY_PATH:
                    return self.prices.copy()
                return history.copy()

            with (
                self.subTest(module=module.__name__),
                patch.object(module.pd, "read_csv", side_effect=read_csv),
                patch.object(portfolio_report, "update_prices") as update,
                redirect_stdout(StringIO()) as output,
            ):
                if module is portfolio_report:
                    module.main(Environment.SCHOOL)
                    update.assert_called_once_with(Environment.SCHOOL)
                else:
                    module.main()
                self.assertIn("Known inventory value (partial): 12.00 EUR", output.getvalue())
                self.assertIn("Total inventory value: unavailable", output.getvalue())

    def test_history_uses_snapshot_quantities_and_never_future_prices(self):
        snapshots = pd.DataFrame({
            "snapshot_date": ["2025-12-01", "2026-01-01", "2026-02-01", "2026-02-01", "2026-03-01"],
            "case_name": ["Alpha", "Alpha", "Alpha", "Beta", "Beta"],
            "quantity": [1, 2, 3, 1, 0],
        })
        result = calculate_historical_portfolio_value(snapshots, self.prices)
        self.assertTrue(pd.isna(result.iloc[0].known_value))
        self.assertTrue(pd.isna(result.iloc[0].total_value))
        self.assertEqual(result.iloc[1].total_value, 8.0)
        self.assertEqual(result.iloc[2].known_value, 12.0)
        self.assertTrue(pd.isna(result.iloc[2].total_value))
        self.assertEqual(result.iloc[2].cases_without_price, 1)
        self.assertEqual(result.iloc[3].total_value, 0.0)

    def test_empty_history_has_summary_columns(self):
        result = calculate_historical_portfolio_value(
            pd.DataFrame(columns=["snapshot_date", "case_name", "quantity"]), self.prices
        )
        self.assertTrue(result.empty)
        self.assertEqual(list(result.columns), [
            "snapshot_date", "known_value", "total_value", "priced_cases",
            "total_cases", "cases_without_price",
        ])

    def test_notebook_weights_and_changes_respect_incomplete_coverage(self):
        notebook = json.loads((PROJECT_ROOT / "notebook/analysis.ipynb").read_text(encoding="utf-8"))
        snapshots = pd.DataFrame({
            "snapshot_date": pd.to_datetime(["2026-01-01", "2026-02-01", "2026-02-01", "2026-03-01", "2026-04-01"]),
            "case_name": ["Alpha", "Alpha", "Beta", "Alpha", "Alpha"],
            "quantity": [1, 2, 1, 3, 6],
        })
        scope = {
            "pd": pd, "np": np, "sys": sys, "PROJECT_ROOT": PROJECT_ROOT,
            "prices": self.prices.assign(date=pd.to_datetime(self.prices.date)),
            "inventory": pd.DataFrame({"case_name": ["Alpha", "Beta"], "quantity": [3, 2]}),
            "snapshots": snapshots, "display": Mock(), "px": Mock(),
        }
        with redirect_stdout(StringIO()):
            for i in (14, 16, 18):
                exec(compile("".join(notebook["cells"][i]["source"]), f"cell_{i}", "exec"), scope)
        self.assertEqual(scope["known_value"], 12.0)
        self.assertEqual(scope["current_value"].iloc[0].weight_pct, 100.0)
        history = scope["portfolio_history"]
        self.assertEqual(history.iloc[1].known_value, 8.0)
        self.assertTrue(pd.isna(history.iloc[1].total_value))
        self.assertTrue(history.change_pct.iloc[:3].isna().all())
        self.assertEqual(history.change_pct.iloc[3], 100.0)


if __name__ == "__main__":
    unittest.main()
