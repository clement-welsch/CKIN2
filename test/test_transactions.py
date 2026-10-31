from pathlib import Path
import tempfile
import unittest

import pandas as pd

from test_multicategory_prices import fixture
from global_snapshots import build_snapshot
from transactions import COLUMNS, import_transactions, reconcile, validate_transactions


class TransactionTests(unittest.TestCase):
    def setup_data(self, root):
        holdings, imported = fixture(root)
        opening = build_snapshot(holdings, imported, "2026-01-01")
        item = holdings.iloc[0]
        def row(key, kind, quantity, date="2026-01-02", **money):
            return dict(transaction_id=key, date=date, item_id=item.item_id, category=item.category,
                        item_name=item.item_name, type=kind, quantity=quantity, currency="EUR",
                        unit_price=money.get("unit_price"), gross_amount=money.get("gross_amount"),
                        fees=money.get("fees"), net_amount=money.get("net_amount"))
        return holdings, opening, row

    def test_partial_sales_drops_transfers_adjustments_and_idempotence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            holdings, opening, row = self.setup_data(root)
            incoming = pd.DataFrame([row("a", "purchase", 3, unit_price=2, gross_amount=6, fees=1, net_amount=7),
                                     row("b", "sale", 1, gross_amount=4, fees=1, net_amount=3),
                                     row("c", "drop", 1, gross_amount=0), row("d", "transfer_out", 2),
                                     row("e", "transfer_in", 1), row("f", "adjustment", -1)])
            path = root / "journal.csv"
            journal = import_transactions(incoming, path, opening)
            before = path.read_bytes()
            import_transactions(incoming, path, opening)
            self.assertEqual(before, path.read_bytes())
            self.assertTrue(pd.isna(journal.loc[journal.transaction_id.eq("d"), "gross_amount"].iloc[0]))
            holdings.loc[0, "quantity"] = 3
            result = reconcile(opening, journal, holdings, "2026-02-01")
            self.assertTrue(result.status.eq("match").all())

    def test_conflict_overselling_and_invalid_money_preserve_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            holdings, opening, row = self.setup_data(root)
            path = root / "journal.csv"
            import_transactions(pd.DataFrame([row("a", "purchase", 1)]), path, opening)
            before = path.read_bytes()
            for candidate in [row("a", "purchase", 2), row("b", "sale", 20),
                              row("c", "purchase", 1, unit_price=2, gross_amount=10),
                              row("d", "drop", 1, gross_amount=5), row("e", "sale", 1, date="2025-12-01")]:
                with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                    import_transactions(pd.DataFrame([candidate]), path, opening)
                self.assertEqual(before, path.read_bytes())

    def test_undated_transactions_and_unknown_costs_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            holdings, opening, row = self.setup_data(Path(directory))
            journal = validate_transactions(pd.DataFrame([row("a", "purchase", 1, date=None)]))
            result = reconcile(opening, journal, holdings, "2026-02-01")
            self.assertEqual(result.iloc[0].status, "undated_transaction")
            self.assertTrue(pd.isna(result.iloc[0].expected_quantity))
            self.assertTrue(pd.isna(journal.iloc[0].gross_amount))

    def test_mismatches_do_not_mutate_observed_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            holdings, opening, row = self.setup_data(Path(directory))
            before = holdings.copy(deep=True)
            journal = pd.DataFrame([row("a", "purchase", 2)])
            result = reconcile(opening, journal, holdings, "2026-02-01")
            self.assertEqual(result.iloc[0].difference, -2)
            self.assertEqual(result.iloc[0].status, "mismatch")
            pd.testing.assert_frame_equal(before, holdings)


if __name__ == "__main__":
    unittest.main()
