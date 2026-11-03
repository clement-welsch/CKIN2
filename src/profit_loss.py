"""Read-only EUR FIFO cost basis and realized/unrealized gains."""

import argparse
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import pandas as pd

from portfolio_data import CATEGORIES, ROOT, _parse_dates, _parse_numbers, load_holdings, load_prices, validate_prices
from transactions import COLUMNS, SIGNS, opening_holdings, reconcile, validate_transactions

CENT = Decimal("0.01")


def money(value):
    return None if pd.isna(value) else Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def complete_sum(values):
    values = list(values)
    return None if any(v is None for v in values) else sum(values, Decimal(0))


def net_amount(row):
    """Only an explicit net or a known gross AND fee defines a net amount."""
    if pd.notna(row.net_amount):
        return money(row.net_amount)
    gross = money(row.gross_amount)
    if gross is None and pd.notna(row.unit_price):
        gross = money(Decimal(str(row.unit_price)) * abs(int(row.quantity)))
    fee = money(row.fees)
    if gross is None or fee is None:
        return None
    net = gross + fee if row.type == "purchase" else gross - fee
    if net < 0:
        raise ValueError("Sale fees cannot exceed proceeds")
    return net


def take(lots, quantity):
    """Allocate remaining lot cost in cents; the final portion gets the residue."""
    consumed = []
    while quantity:
        if not lots:
            raise ValueError("FIFO outflow exceeds available quantity")
        lot = lots[0]
        count = min(quantity, lot["quantity"])
        cost = None if lot["cost"] is None else money(lot["cost"] * count / lot["quantity"])
        consumed.append({**lot, "quantity": count, "cost": cost})
        lot["quantity"] -= count
        if cost is not None:
            lot["cost"] -= cost
        quantity -= count
        if lot["quantity"] == 0:
            lots.pop(0)
    return consumed


def calculate(opening, journal, prices, when, *, opening_costs=None, transfer_links=None,
              observed=None, observed_imported=None, estimated_sell_fee_rate=None):
    """Return item/sale/category/global tables, without changing any input frame.

    Optional opening_costs: item_id,total_cost (EUR including known buy fees).
    Optional transfer_links: out_id,in_id; exact full-quantity internal transfers.
    Same-instant item movements are ambiguous and deliberately not ordered by ID.
    """
    baseline, start, unavailable = opening_holdings(opening)
    journal, prices = validate_transactions(journal), validate_prices(prices)
    cutoff = _parse_dates(pd.Series([when]), "valuation date").iloc[0]
    if cutoff < start or journal.date.dropna().lt(start).any():
        raise ValueError("Valuation/journal must not precede opening inventory")
    try:
        rate = None if estimated_sell_fee_rate is None else Decimal(str(estimated_sell_fee_rate))
    except InvalidOperation as error:
        raise ValueError("Expected a numeric estimated sale fee rate") from error
    if rate is not None and (not rate.is_finite() or not 0 <= rate <= 1):
        raise ValueError("Estimated sale fee rate must be between zero and one")
    costs = {}
    if opening_costs is not None:
        if not {"item_id", "total_cost"}.issubset(opening_costs) or opening_costs.item_id.duplicated().any():
            raise ValueError("Opening costs require unique item_id,total_cost")
        validated = _parse_numbers(opening_costs.total_cost, "opening total_cost")
        for key, cost in zip(opening_costs.item_id, validated):
            held = baseline.loc[baseline.item_id.eq(key), "quantity"]
            if held.empty or pd.isna(held.iloc[0]) or (held.iloc[0] == 0 and pd.notna(cost) and cost != 0):
                raise ValueError("Opening costs require a known opening quantity")
            costs[key] = money(cost)

    links = {}
    if transfer_links is not None:
        if not {"out_id", "in_id"}.issubset(transfer_links) or transfer_links.out_id.duplicated().any() or transfer_links.in_id.duplicated().any():
            raise ValueError("Transfer links require unique out_id,in_id")
        by_id = journal.set_index("transaction_id")
        for link in transfer_links.itertuples(index=False):
            if link.out_id not in by_id.index or link.in_id not in by_id.index:
                raise ValueError("Unknown linked transfer transaction")
            out, incoming = by_id.loc[link.out_id], by_id.loc[link.in_id]
            if (out.type != "transfer_out" or incoming.type != "transfer_in" or out.item_id != incoming.item_id
                    or out.quantity != incoming.quantity or pd.isna(out.date) or pd.isna(incoming.date)
                    or out.date >= incoming.date):
                raise ValueError("Linked transfers need same item/quantity and an earlier outflow")
            links[link.in_id] = link.out_id

    eligible = journal.loc[journal.date.le(cutoff) | journal.date.isna()]
    metadata = pd.concat([baseline[["item_id", "category", "item_name"]], eligible[["item_id", "category", "item_name"]]])
    if observed is not None:
        reconciliation = reconcile(opening, journal, observed, cutoff, observed_imported=observed_imported)
        metadata = pd.concat([metadata, observed[["item_id", "category", "item_name"]]])
    else:
        reconciliation = None
    latest = prices.loc[prices.date.le(cutoff) & prices.unit_price.notna()].sort_values("date", kind="stable").drop_duplicates("item_id", keep="last").set_index("item_id")
    items, sales = [], []
    for item in metadata.drop_duplicates("item_id").itertuples(index=False):
        movements = eligible.loc[eligible.item_id.eq(item.item_id)].sort_values("date", kind="stable")
        base = baseline.loc[baseline.item_id.eq(item.item_id), "quantity"]
        quantity = base.iloc[0] if len(base) else 0
        reason = ("unknown_opening_quantity" if item.category in unavailable or pd.isna(quantity)
                  else "undated_transaction" if movements.date.isna().any()
                  else "ambiguous_simultaneous_movements" if movements.date.duplicated().any() else "")
        lots, stored = [], {}
        if not reason and quantity:
            lots.append(dict(quantity=int(quantity), cost=costs.get(item.item_id), date=start, order=-1))
        item_sales = []
        if not reason:
            for order, row in enumerate(movements.itertuples(index=False)):
                qty = int(row.quantity)
                delta = qty * SIGNS[row.type]
                if delta > 0:
                    if row.type == "transfer_in" and row.transaction_id in links:
                        source = links[row.transaction_id]
                        if source not in stored:
                            reason = "unavailable_transfer_origin"
                            break
                        lots.extend(stored.pop(source))
                    else:
                        cost = Decimal(0) if row.type == "drop" else net_amount(row) if row.type == "purchase" else None
                        lots.append(dict(quantity=delta, cost=cost, date=row.date, order=order))
                    lots.sort(key=lambda lot: (lot["date"], lot["order"]))
                else:
                    removed = take(lots, -delta)
                    if row.type == "transfer_out":
                        stored[row.transaction_id] = removed
                    if row.type == "sale":
                        basis = complete_sum(lot["cost"] for lot in removed)
                        proceeds = net_amount(row)
                        gain = None if basis is None or proceeds is None else proceeds - basis
                        item_sales.append(dict(transaction_id=row.transaction_id, item_id=item.item_id, category=item.category,
                                               quantity=qty, net_proceeds=proceeds, cost_basis=basis, realized_gain=gain,
                                               roi_pct=gain / basis * 100 if gain is not None and basis else None))
        if reason:
            lots = []
            item_sales = [dict(transaction_id=r.transaction_id, item_id=item.item_id, category=item.category,
                               quantity=r.quantity, net_proceeds=net_amount(r), cost_basis=None, realized_gain=None, roi_pct=None)
                          for r in movements.loc[movements.type.eq("sale")].itertuples(index=False)]
        sales.extend(item_sales)
        quantity = None if reason else sum(lot["quantity"] for lot in lots)
        basis = None if reason else complete_sum(lot["cost"] for lot in lots)
        known_basis = None if reason else sum((lot["cost"] for lot in lots if lot["cost"] is not None), Decimal(0))
        known_qty = 0 if reason else sum(lot["quantity"] for lot in lots if lot["cost"] is not None)
        status = reason
        if reconciliation is not None:
            match = reconciliation.loc[reconciliation.item_id.eq(item.item_id), "status"]
            if len(match) and match.iloc[0] != "match":
                status = status or "inventory_" + match.iloc[0]
        price = money(latest.loc[item.item_id, "unit_price"]) if item.item_id in latest.index else None
        # Round market totals, not each unit: prices may have sub-cent precision.
        gross = Decimal(0) if quantity == 0 else money(Decimal(str(latest.loc[item.item_id, "unit_price"])) * quantity) if price is not None and quantity is not None else None
        if status:
            basis, known_basis, gross = None, None, None
            known_qty = 0
        latent = gross - basis if gross is not None and basis is not None else None
        net = money(gross * (1 - rate)) if gross is not None and rate is not None else None
        realized = None if reason else complete_sum(s["realized_gain"] for s in item_sales)
        items.append(dict(item_id=item.item_id, category=item.category, item_name=item.item_name,
                          quantity=quantity, cost_known_quantity=known_qty,
                          price_date=latest.loc[item.item_id, "date"] if item.item_id in latest.index else pd.NaT,
                          remaining_cost=basis, known_remaining_cost=known_basis, gross_market_value=gross,
                          estimated_net_proceeds=net, unrealized_gain=latent,
                          estimated_net_gain=net - basis if net is not None and basis is not None else None,
                          roi_pct=latent / basis * 100 if latent is not None and basis else None,
                          realized_gain=realized,
                          known_realized_gain=sum((s["realized_gain"] for s in item_sales if s["realized_gain"] is not None), Decimal(0)) if not reason else None,
                          sales_count=len(item_sales), known_sales_count=sum(s["realized_gain"] is not None for s in item_sales),
                          status=status or ("unknown_remaining_cost" if basis is None else "ok")))
    item_frame = pd.DataFrame(items, columns=["item_id", "category", "item_name", "quantity", "cost_known_quantity", "price_date",
                                            "remaining_cost", "known_remaining_cost", "gross_market_value", "estimated_net_proceeds",
                                            "unrealized_gain", "estimated_net_gain", "roi_pct", "realized_gain", "known_realized_gain",
                                            "sales_count", "known_sales_count", "status"])
    sale_frame = pd.DataFrame(sales, columns=["transaction_id", "item_id", "category", "quantity", "net_proceeds", "cost_basis", "realized_gain", "roi_pct"])
    summaries = []
    imported = set(observed_imported) if observed_imported is not None else set(CATEGORIES) - unavailable
    for category in [*CATEGORIES, "global"]:
        group = item_frame if category == "global" else item_frame.loc[item_frame.category.eq(category)] if not item_frame.empty else item_frame
        missing = len(set(CATEGORIES) - imported) if category == "global" else int(category not in imported)
        opening_missing = len(unavailable) if category == "global" else int(category in unavailable)
        row = dict(category=category, categories_not_imported=missing, opening_categories_not_imported=opening_missing,
                   estimated_sell_fee_rate=None if rate is None else float(rate))
        for field in ("remaining_cost", "known_remaining_cost", "gross_market_value", "estimated_net_proceeds", "unrealized_gain", "estimated_net_gain", "realized_gain", "known_realized_gain"):
            values = group[field].tolist() if len(group) else []
            if field.startswith("known_"):
                known = [v for v in values if v is not None]
                row[field] = sum(known, Decimal(0)) if known or (not values and not missing) else None
            else:
                row[field] = None if missing else complete_sum(values)
            if field in ("estimated_net_proceeds", "estimated_net_gain") and rate is None:
                row[field] = None
            if field == "realized_gain" and opening_missing:
                row[field] = None
        row["sales_count"] = int(group.sales_count.sum()) if len(group) else 0
        row["known_sales_count"] = int(group.known_sales_count.sum()) if len(group) else 0
        row["cost_known_quantity"] = int(group.cost_known_quantity.sum()) if len(group) else 0
        row["unavailable_items"] = int((~group.status.isin(["ok", "unknown_remaining_cost"])).sum()) if len(group) else 0
        row["quantity"] = None if len(group) and group.quantity.isna().any() else int(group.quantity.sum()) if len(group) else 0
        row["cost_coverage_pct"] = None if missing or row["quantity"] is None or row["unavailable_items"] else row["cost_known_quantity"] / row["quantity"] * 100 if row["quantity"] else 100.0
        cost, gain = row["remaining_cost"], row["unrealized_gain"]
        row["roi_pct"] = gain / cost * 100 if gain is not None and cost else None
        summaries.append(row)
    # Public tables use floats/NaN for standard pandas/report interoperability.
    def numeric(frame):
        return frame.map(lambda value: float(value) if isinstance(value, Decimal) else value)
    return dict(items=numeric(item_frame), sales=numeric(sale_frame), summary=numeric(pd.DataFrame(summaries)))


def report(root=ROOT, when=None, estimated_sell_fee_rate=None):
    root = Path(root)
    directory = root / "data/processed"
    holdings, imported = load_holdings(root)
    journal_path = directory / "transactions.csv"
    journal = pd.read_csv(journal_path) if journal_path.exists() else pd.DataFrame(columns=COLUMNS)
    def optional(name):
        path = directory / name
        return pd.read_csv(path) if path.exists() else None
    result = calculate(pd.read_csv(directory / "opening_inventory.csv"), journal,
                       load_prices(root, holdings), when if when is not None else pd.Timestamp.now(),
                       opening_costs=optional("opening_costs.csv"), transfer_links=optional("transfer_links.csv"),
                       observed=holdings, observed_imported=imported, estimated_sell_fee_rate=estimated_sell_fee_rate)
    print("FIFO EUR report; N/A means unknown, not zero. Gross gains exclude estimated sale fees.")
    for label, frame in result.items():
        print(f"\n{label}\n{frame.to_string(index=False, na_rep='N/A')}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--date", help="Exact local valuation cutoff")
    parser.add_argument("--estimated-sell-fee-rate", type=float, help="Fraction, e.g. 0.15; estimate only")
    args = parser.parse_args()
    report(args.root, args.date, args.estimated_sell_fee_rate)
