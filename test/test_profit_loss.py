"""Synthetic FIFO examples, cost coverage and strict read-only reporting."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from test_multicategory_prices import fixture
from global_snapshots import build_snapshot
from portfolio_data import CATEGORIES, HOLDINGS, PRICES, identity
from transactions import COLUMNS
from profit_loss import calculate, report


class ProfitLossTests(unittest.TestCase):
    def setUp(self):
        self.key = identity("case", "Alpha")
        self.empty = pd.DataFrame(columns=HOLDINGS)
        self.opening = build_snapshot(self.empty, set(CATEGORIES), "2026-01-01")
        self.prices = pd.DataFrame([dict(date="2026-02-01", item_id=self.key, category="case", item_name="Alpha",
                                         unit_price=10, source="steam", currency="EUR", date_estimated=False)], columns=PRICES)

    def tx(self, key, kind, quantity, date="2026-01-02", **money):
        return dict(transaction_id=key, date=date, item_id=self.key, category="case", item_name="Alpha",
                    type=kind, quantity=quantity, currency="EUR", unit_price=money.get("unit_price"),
                    gross_amount=money.get("gross_amount"), fees=money.get("fees"), net_amount=money.get("net_amount"))

    def value(self, rows, **options):
        return calculate(self.opening, pd.DataFrame(rows, columns=COLUMNS), self.prices, "2026-02-01", **options)

    def test_fifo_partial_sale_buy_fees_and_estimated_sell_fees(self):
        result = self.value([
            self.tx("a", "purchase", 2, gross_amount=6, fees=1),
            self.tx("b", "purchase", 3, date="2026-01-03", net_amount=15),
            self.tx("c", "sale", 3, date="2026-01-04", gross_amount=30, fees=3),
        ], estimated_sell_fee_rate=.1)
        item, sale = result["items"].iloc[0], result["sales"].iloc[0]
        self.assertEqual(sale.cost_basis, 12)
        self.assertEqual(sale.realized_gain, 15)
        self.assertEqual(item.remaining_cost, 10)
        self.assertEqual(item.gross_market_value, 20)
        self.assertEqual(item.unrealized_gain, 10)
        self.assertEqual(item.estimated_net_proceeds, 18)
        self.assertEqual(item.estimated_net_gain, 8)
        self.assertEqual(item.roi_pct, 100)
        totals = result["summary"].set_index("category")
        self.assertEqual(totals.loc["global", "realized_gain"], 15)
        self.assertEqual(totals.loc["global", "remaining_cost"], totals.loc[list(CATEGORIES), "remaining_cost"].sum())

    def test_cent_rounding_allocates_residue_without_losing_cost(self):
        result = self.value([self.tx("a", "purchase", 3, net_amount=1),
                             self.tx("b", "sale", 1, date="2026-01-03", net_amount=1),
                             self.tx("c", "sale", 1, date="2026-01-04", net_amount=1),
                             self.tx("d", "sale", 1, date="2026-01-05", net_amount=1)])
        self.assertEqual(result["sales"].cost_basis.tolist(), [.33, .34, .33])
        self.assertAlmostEqual(result["sales"].cost_basis.sum(), 1)
        self.assertEqual(result["items"].remaining_cost.iloc[0], 0)

    def test_drops_have_zero_cost_but_unknown_buy_fees_are_not_zero(self):
        dropped = self.value([self.tx("a", "drop", 1)])
        self.assertEqual(dropped["items"].remaining_cost.iloc[0], 0)
        self.assertTrue(pd.isna(dropped["items"].roi_pct.iloc[0]))
        unknown = self.value([self.tx("a", "purchase", 1, gross_amount=2)])
        self.assertTrue(pd.isna(unknown["items"].remaining_cost.iloc[0]))
        self.assertEqual(unknown["summary"].set_index("category").loc["global", "cost_coverage_pct"], 0)
        self.assertTrue(pd.isna(unknown["items"].estimated_net_proceeds.iloc[0]))

    def test_unknown_opening_cost_and_explicit_cost(self):
        self.opening = build_snapshot(pd.DataFrame([dict(item_id=self.key, category="case", item_name="Alpha", quantity=2)]), set(CATEGORIES), "2026-01-01")
        rows = [self.tx("a", "sale", 1, net_amount=5)]
        self.assertTrue(pd.isna(self.value(rows)["sales"].realized_gain.iloc[0]))
        costs = pd.DataFrame({"item_id": [self.key], "total_cost": [6]})
        result = self.value(rows, opening_costs=costs)
        self.assertEqual(result["sales"].realized_gain.iloc[0], 2)
        self.assertEqual(result["items"].remaining_cost.iloc[0], 3)

    def test_internal_transfer_preserves_original_lot_cost(self):
        rows = [self.tx("a", "purchase", 2, net_amount=6),
                self.tx("out", "transfer_out", 1, date="2026-01-03"),
                self.tx("in", "transfer_in", 1, date="2026-01-04"),
                self.tx("sale", "sale", 2, date="2026-01-05", net_amount=10)]
        links = pd.DataFrame({"out_id": ["out"], "in_id": ["in"]})
        self.assertTrue(pd.isna(self.value(rows)["sales"].realized_gain.iloc[0]))
        result = self.value(rows, transfer_links=links)
        self.assertEqual(result["sales"].cost_basis.iloc[0], 6)
        self.assertEqual(result["sales"].realized_gain.iloc[0], 4)

    def test_undated_or_simultaneous_movements_do_not_invent_fifo_order(self):
        for date in (None, "2026-01-02"):
            result = self.value([self.tx("a", "purchase", 2, net_amount=4), self.tx("b", "sale", 1, date=date, net_amount=5)])
            self.assertTrue(pd.isna(result["items"].remaining_cost.iloc[0]))
            self.assertTrue(pd.isna(result["sales"].realized_gain.iloc[0]))
            self.assertNotEqual(result["items"].status.iloc[0], "ok")

    def test_adjustments_and_partial_known_cost_coverage(self):
        result = self.value([self.tx("a", "purchase", 2, net_amount=4),
                             self.tx("b", "adjustment", -1, date="2026-01-03"),
                             self.tx("c", "adjustment", 1, date="2026-01-04")])
        item = result["items"].iloc[0]
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.known_remaining_cost, 2)
        self.assertTrue(pd.isna(item.remaining_cost))
        self.assertEqual(result["summary"].set_index("category").loc["global", "cost_coverage_pct"], 50)

    def test_future_prices_and_transactions_are_excluded(self):
        future = self.prices.copy()
        future["date"] = "2026-03-01"
        result = calculate(self.opening, pd.DataFrame([self.tx("a", "purchase", 1, net_amount=2), self.tx("b", "sale", 1, date="2026-03-01", net_amount=5)]), future, "2026-02-01")
        self.assertEqual(result["items"].quantity.iloc[0], 1)
        self.assertTrue(result["sales"].empty)
        self.assertTrue(pd.isna(result["items"].unrealized_gain.iloc[0]))

    def test_empty_and_unimported_categories_have_distinct_totals(self):
        result = self.value([])
        self.assertEqual(result["summary"].remaining_cost.tolist(), [0] * 7)
        self.opening = build_snapshot(self.empty, {"case"}, "2026-01-01")
        result = self.value([])["summary"].set_index("category")
        self.assertEqual(result.loc["case", "remaining_cost"], 0)
        self.assertTrue(pd.isna(result.loc["global", "remaining_cost"]))

    def test_missing_opening_category_cannot_claim_zero_realized_gain(self):
        self.opening = build_snapshot(self.empty, {"case"}, "2026-01-01")
        totals = self.value([], observed=self.empty, observed_imported=set(CATEGORIES))["summary"].set_index("category")
        self.assertEqual(totals.loc["skin", "remaining_cost"], 0)
        self.assertTrue(pd.isna(totals.loc["skin", "realized_gain"]))
        self.assertTrue(pd.isna(totals.loc["global", "realized_gain"]))
        self.assertEqual(totals.loc["global", "opening_categories_not_imported"], 5)

    def test_negative_inventory_invalid_rates_and_transfer_links_fail(self):
        with self.assertRaises(ValueError):
            self.value([self.tx("a", "sale", 1, net_amount=5)])
        for rate in (-.1, 1.1, float("nan"), True):
            with self.assertRaises(ValueError):
                self.value([], estimated_sell_fee_rate=rate)
        with self.assertRaises(ValueError):
            self.value([], transfer_links=pd.DataFrame({"out_id": ["missing"], "in_id": ["missing"]}))

    def test_missing_sale_fees_and_unknown_costs_remain_partial(self):
        result = self.value([self.tx("a", "purchase", 2, net_amount=4),
                             self.tx("b", "sale", 1, date="2026-01-03", gross_amount=5)])
        self.assertTrue(pd.isna(result["sales"].net_proceeds.iloc[0]))
        self.assertTrue(pd.isna(result["items"].realized_gain.iloc[0]))
        self.assertEqual(result["items"].remaining_cost.iloc[0], 2)
        totals = result["summary"].set_index("category")
        self.assertTrue(pd.isna(totals.loc["global", "realized_gain"]))
        self.assertEqual(totals.loc["global", "sales_count"], 1)
        self.assertEqual(totals.loc["global", "known_sales_count"], 0)

    def test_partial_aggregates_keep_known_subtotals_across_items(self):
        second = identity("skin", "Beta")
        rows = [self.tx("a", "purchase", 1, net_amount=2),
                {**self.tx("b", "purchase", 1, gross_amount=4), "item_id": second, "category": "skin", "item_name": "Beta"}]
        result = self.value(rows)
        totals = result["summary"].set_index("category")
        self.assertEqual(totals.loc["global", "known_remaining_cost"], 2)
        self.assertTrue(pd.isna(totals.loc["global", "remaining_cost"]))
        self.assertEqual(totals.loc["global", "cost_coverage_pct"], 50)
        self.assertEqual(totals.loc["global", "known_remaining_cost"], totals.loc[list(CATEGORIES), "known_remaining_cost"].sum())

    def test_inputs_are_not_mutated_and_empty_outputs_have_a_stable_schema(self):
        journal = pd.DataFrame([self.tx("a", "purchase", 2, net_amount=4)], columns=COLUMNS)
        before = [f.copy(deep=True) for f in (self.opening, journal, self.prices)]
        calculate(self.opening, journal, self.prices, "2026-02-01")
        for old, current in zip(before, (self.opening, journal, self.prices)):
            pd.testing.assert_frame_equal(old, current)
        empty = self.value([])
        self.assertIn("remaining_cost", empty["items"])
        self.assertIn("realized_gain", empty["sales"])

    def test_report_reconciliation_is_read_only_and_mismatch_suppresses_latent_gain(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            holdings, imported = fixture(root)
            build_snapshot(holdings, imported, "2026-01-01").to_csv(root / "data/processed/opening_inventory.csv", index=False)
            original = {p: p.read_bytes() for p in root.rglob("*.csv")}
            with redirect_stdout(StringIO()):
                report(root, "2026-02-01")
            self.assertEqual(original, {p: p.read_bytes() for p in root.rglob("*.csv")})
        observed = pd.DataFrame([dict(item_id=self.key, category="case", item_name="Alpha", quantity=5)])
        result = self.value([self.tx("a", "purchase", 1, net_amount=2)], observed=observed)
        self.assertEqual(result["items"].status.iloc[0], "inventory_mismatch")
        self.assertTrue(pd.isna(result["items"].unrealized_gain.iloc[0]))
        self.assertTrue(pd.isna(result["summary"].set_index("category").loc["global", "cost_coverage_pct"]))

    def test_returned_transfer_keeps_original_fifo_age(self):
        rows = [self.tx("a", "purchase", 1, net_amount=2),
                self.tx("out", "transfer_out", 1, date="2026-01-03"),
                self.tx("b", "purchase", 1, date="2026-01-04", net_amount=8),
                self.tx("in", "transfer_in", 1, date="2026-01-05"),
                self.tx("sale", "sale", 1, date="2026-01-06", net_amount=10)]
        result = self.value(rows, transfer_links=pd.DataFrame({"out_id": ["out"], "in_id": ["in"]}))
        self.assertEqual(result["sales"].cost_basis.iloc[0], 2)
        self.assertEqual(result["items"].remaining_cost.iloc[0], 8)

    def test_unknown_opening_quantity_and_subcent_market_price(self):
        self.opening = build_snapshot(pd.DataFrame([dict(item_id=self.key, category="case", item_name="Alpha", quantity=None)]), set(CATEGORIES), "2026-01-01")
        result = self.value([])
        self.assertTrue(pd.isna(result["summary"].set_index("category").loc["global", "remaining_cost"]))
        self.opening = build_snapshot(self.empty, set(CATEGORIES), "2026-01-01")
        self.prices["unit_price"] = .004
        result = self.value([self.tx("a", "drop", 3)])
        self.assertEqual(result["items"].gross_market_value.iloc[0], .01)

    def test_unknown_opening_lot_does_not_hide_later_known_sale(self):
        self.opening = build_snapshot(pd.DataFrame([dict(item_id=self.key, category="case", item_name="Alpha", quantity=1)]), set(CATEGORIES), "2026-01-01")
        result = self.value([self.tx("buy", "purchase", 2, net_amount=4),
                             self.tx("first", "sale", 1, date="2026-01-03", net_amount=5),
                             self.tx("second", "sale", 1, date="2026-01-04", net_amount=5)])
        self.assertTrue(pd.isna(result["sales"].realized_gain.iloc[0]))
        self.assertEqual(result["sales"].realized_gain.iloc[1], 3)
        self.assertEqual(result["items"].remaining_cost.iloc[0], 2)
        total = result["summary"].set_index("category").loc["global"]
        self.assertTrue(pd.isna(total.realized_gain))
        self.assertEqual(total.known_realized_gain, 3)
        self.assertEqual(total.known_sales_count, 1)


if __name__ == "__main__":
    unittest.main()
