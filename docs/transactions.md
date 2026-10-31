# Transaction journal (#25)

```powershell
python src/transactions.py init-opening --date 2026-10-31T12:00:00
python src/transactions.py import path/to/new_transactions.csv
python src/transactions.py reconcile --date 2026-11-30T23:59:59
```

The first command takes current quantities as an explicit opening balance. Use
the real observation timestamp, then record only subsequent movements. It never
invents past purchases. Existing opening balances cannot be overwritten by this
command. All journal, opening and incoming CSVs are private and must stay out of Git.

Columns: transaction_id,date,item_id,category,item_name,type,quantity,currency,
unit_price,gross_amount,fees,net_amount. IDs match the shared UUID5 identity.
Types: purchase, sale, drop, transfer_in, transfer_out and adjustment. Quantities
are positive whole units except signed, nonzero adjustments. Every transaction
has a unique manually assigned ID. Missing dates and costs are allowed and stay
unknown. A drop is explicitly free; an unknown purchase cost is not zero.

EUR is the only supported currency. Unit prices exclude fees. Gross amount is
the positive total before fees. Fees are positive totals. For purchases, net
amount is cash paid (gross + fees); for sales it is proceeds (gross - fees).
Supplied monetary fields must agree within half a cent. No monetary amount is
inferred from an acquisition reference. No profit or tax calculation is provided.

Synthetic example (substitute the identity from your catalog):

```text
transaction_id,date,item_id,category,item_name,type,quantity,currency,unit_price,gross_amount,fees,net_amount
purchase-001,2026-11-01T12:00:00,<catalog UUID>,case,Recoil,purchase,2,EUR,1.50,3.00,0.10,3.10
drop-001,2026-11-02T12:00:00,<catalog UUID>,case,Recoil,drop,1,EUR,0,0,0,0
```

Use import for one or multiple rows. Exact repeated IDs are a no-op; conflicting
reused IDs reject the entire batch. All rows and the existing journal are
validated before atomic replacement. Known dated movements cannot precede the
opening inventory or produce a negative quantity. Movements at the exact same
timestamp are netted as a batch. Concurrent writers are unsupported.

Reconciliation compares opening + movements through the requested timestamp to
the supplied/current inventory, without modifying either. Undated movements,
unknown opening quantities and unknown observed quantities produce explicit
unavailable results. Use an observation timestamp matching the actual inventory;
this command does not reconstruct an arbitrary historical inventory. An item
absent from an observed imported category is interpreted as zero. Imported
category completeness is required when interpreting the result.
