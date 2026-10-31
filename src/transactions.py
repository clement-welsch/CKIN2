"""Validated transaction journal and explicit opening-balance reconciliation."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from global_snapshots import build_snapshot, validate_snapshots
from portfolio_data import HOLDINGS, ROOT, _parse_dates, _parse_numbers, atomic_csv, identity, load_holdings, validate_holdings

COLUMNS = ["transaction_id", "date", "item_id", "category", "item_name", "type", "quantity",
           "currency", "unit_price", "gross_amount", "fees", "net_amount"]
SIGNS = {"purchase": 1, "sale": -1, "drop": 1, "transfer_in": 1, "transfer_out": -1, "adjustment": 1}


def validate_transactions(frame):
    if not set(COLUMNS).issubset(frame):
        raise ValueError("Missing transaction columns")
    result = frame[COLUMNS].copy().reset_index(drop=True)
    for row in result.itertuples(index=False):
        if not isinstance(row.transaction_id, str) or not row.transaction_id or row.transaction_id != row.transaction_id.strip():
            raise ValueError("Each transaction needs a nonblank stable ID")
        if row.item_id != identity(row.category, row.item_name) or row.type not in SIGNS:
            raise ValueError("Invalid identity or transaction type")
    if result.transaction_id.duplicated().any():
        raise ValueError("Duplicate transaction IDs")
    present = result.date.notna()
    parsed = pd.Series(pd.NaT, index=result.index, dtype="datetime64[ns]")
    parsed.loc[present] = _parse_dates(result.loc[present, "date"], "transaction date")
    result["date"] = parsed
    if result.quantity.map(lambda v: isinstance(v, bool)).any():
        raise ValueError("Boolean quantity")
    result["quantity"] = pd.to_numeric(result.quantity, errors="raise")
    if not np.isfinite(result.quantity).all() or (result.quantity % 1 != 0).any() or result.quantity.eq(0).any():
        raise ValueError("Transaction quantities must be nonzero finite whole numbers")
    if (result.loc[result.type.ne("adjustment"), "quantity"] < 0).any():
        raise ValueError("Only adjustments use signed quantities")
    if not result.currency.eq("EUR").all():
        raise ValueError("Only EUR is supported; no implicit currency conversion")
    for column in ["unit_price", "gross_amount", "fees", "net_amount"]:
        result[column] = _parse_numbers(result[column], column)
    # Optional monetary fields stay unknown. Supplied fields must agree to a cent.
    for row in result.itertuples(index=False):
        if pd.notna(row.unit_price) and pd.notna(row.gross_amount) and not np.isclose(abs(row.quantity) * row.unit_price, row.gross_amount, rtol=0, atol=.005):
            raise ValueError("Unit and gross prices disagree")
        if row.type == "drop" and any(pd.notna(v) and v != 0 for v in (row.unit_price, row.gross_amount, row.fees, row.net_amount)):
            raise ValueError("A free drop cannot have a paid acquisition cost")
        if row.type in ("purchase", "sale") and pd.notna(row.gross_amount) and pd.notna(row.fees) and pd.notna(row.net_amount):
            expected = row.gross_amount + row.fees if row.type == "purchase" else row.gross_amount - row.fees
            if expected < 0 or not np.isclose(expected, row.net_amount, rtol=0, atol=.005):
                raise ValueError("Gross, fees and net amounts disagree")
    return result


def opening_holdings(opening):
    opening = validate_snapshots(opening)
    if opening.snapshot_date.nunique() != 1:
        raise ValueError("Opening inventory must represent exactly one instant")
    stamp = opening.snapshot_date.iloc[0]
    holdings = opening.loc[opening.state.eq("holdings"), HOLDINGS]
    unavailable = set(opening.loc[opening.state.eq("not_imported"), "category"])
    return holdings, stamp, unavailable


def reconcile(opening, journal, observed, when):
    baseline, start, unavailable = opening_holdings(opening)
    journal, observed = validate_transactions(journal), validate_holdings(observed)
    end = _parse_dates(pd.Series([when]), "reconciliation date").iloc[0]
    if end < start:
        raise ValueError("Reconciliation precedes opening inventory")
    if journal.date.dropna().lt(start).any():
        raise ValueError("Journal transactions must not precede the opening balance")
    metadata = pd.concat([baseline[HOLDINGS[:3]], observed[HOLDINGS[:3]], journal[HOLDINGS[:3]]]).drop_duplicates("item_id")
    base = baseline.set_index("item_id").quantity
    actual = observed.set_index("item_id").quantity
    rows = []
    for item in metadata.itertuples(index=False):
        movements = journal.loc[journal.item_id.eq(item.item_id)]
        value = base.get(item.item_id, 0.0)
        reason = ""
        if item.category in unavailable or pd.isna(value):
            reason = "unknown_opening_quantity"
        elif movements.date.isna().any():
            reason = "undated_transaction"
        else:
            movements = movements.loc[movements.date.le(end)].copy()
            movements["delta"] = movements.quantity * movements.type.map(SIGNS)
            # Simultaneous movements form one net batch; no invented intra-batch order.
            trajectory = movements.groupby("date").delta.sum().sort_index().cumsum() + value
            if (trajectory < 0).any():
                raise ValueError(f"Negative inventory after transactions for {item.item_name}")
            value += movements.delta.sum()
        expected = float("nan") if reason else value
        current = actual.get(item.item_id, 0.0)
        difference = current - expected
        status = reason or ("unknown_observed_quantity" if pd.isna(current) else "match" if difference == 0 else "mismatch")
        rows.append(dict(item_id=item.item_id, category=item.category, item_name=item.item_name,
                         expected_quantity=expected, observed_quantity=current, difference=difference, status=status))
    return pd.DataFrame(rows, columns=["item_id", "category", "item_name", "expected_quantity", "observed_quantity", "difference", "status"])


def import_transactions(incoming, path, opening):
    incoming = validate_transactions(incoming)
    previous = validate_transactions(pd.read_csv(path)) if path.exists() else pd.DataFrame(columns=COLUMNS)
    common = set(incoming.transaction_id) & set(previous.transaction_id)
    for key in common:
        old = previous.loc[previous.transaction_id.eq(key)].reset_index(drop=True)
        new = incoming.loc[incoming.transaction_id.eq(key)].reset_index(drop=True)
        # Type differences after CSV round trips do not make a transaction different.
        try:
            pd.testing.assert_frame_equal(old, new, check_dtype=False)
        except AssertionError as error:
            raise ValueError(f"Conflicting transaction ID: {key}") from error
    combined = validate_transactions(pd.concat([previous, incoming.loc[~incoming.transaction_id.isin(common)]], ignore_index=True))
    _, stamp, _ = opening_holdings(opening)
    end = max([stamp, *combined.date.dropna().tolist()])
    reconcile(opening, combined, pd.DataFrame(columns=HOLDINGS), end)
    combined = combined.sort_values(["date", "transaction_id"], kind="stable", na_position="last").reset_index(drop=True)
    atomic_csv(combined, path)
    return combined


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    initial = commands.add_parser("init-opening")
    initial.add_argument("--date", required=True, help="Actual opening-balance timestamp; no historical reconstruction")
    ingest = commands.add_parser("import")
    ingest.add_argument("csv", type=Path)
    check = commands.add_parser("reconcile")
    check.add_argument("--date", required=True)
    args = parser.parse_args()
    directory = ROOT / "data/processed"
    opening_path, journal_path = directory / "opening_inventory.csv", directory / "transactions.csv"
    if args.command == "init-opening":
        if opening_path.exists():
            parser.error("Opening inventory already exists; it will not be overwritten")
        holdings, imported = load_holdings()
        atomic_csv(build_snapshot(holdings, imported, args.date), opening_path)
    else:
        opening = pd.read_csv(opening_path)
        if args.command == "import":
            import_transactions(pd.read_csv(args.csv), journal_path, opening)
        else:
            journal = pd.read_csv(journal_path) if journal_path.exists() else pd.DataFrame(columns=COLUMNS)
            print(reconcile(opening, journal, load_holdings()[0], args.date).to_string(index=False, na_rep="N/A"))


if __name__ == "__main__":
    main()
