# FIFO gains and losses (#35)

This read-only EUR report uses the opening inventory, transaction journal and
saved market prices. It does not import transactions, change quantities, collect
prices or write CSVs. It is an analytical cost calculation, not a tax statement.

```powershell
.\.venv\Scripts\python.exe src/profit_loss.py
.\.venv\Scripts\python.exe src/profit_loss.py --date 2026-11-03T18:00:00 --estimated-sell-fee-rate 0.15
```

`--root` selects the project containing `data/processed`. A date is an exact
machine-local, timezone-naive cutoff. Later prices and dated transactions are
excluded. Undated transactions cannot safely be assigned before/after the cutoff
and therefore make that item's FIFO history unavailable.

## Inputs and explicit opening costs

Initialize `opening_inventory.csv` and import `transactions.csv` with the
[transaction journal](transactions.md). The report reconciles computed quantities
against the current inventory before publishing latent gains. For a historical
cutoff, a mismatch against today's inventory is expected unless the quantities
are unchanged; the calculation API can instead accept a matching observed frame
or omit this check for a ledger-only analysis.

An opening inventory records quantities, not acquisition costs. Costs are unknown
by default. An optional private `opening_costs.csv` supplies:

```csv
item_id,total_cost
<existing stable item UUID>,12.34
```

`total_cost` is the **total** EUR cost including known acquisition fees for that
item's entire opening quantity. Do not use today's market price as a substitute
for its unknown historical purchase cost. Item IDs must belong to the opening
inventory, be unique and have a known opening quantity. Zero quantity can only
have zero or unknown cost. A missing cost row remains unknown.

## FIFO and cent allocation

The oldest available acquisition lot is consumed first, including partial sales.
For example, buy 2 items for EUR 7 including fees, then 3 for EUR 15. Selling 3
consumes the first EUR 7 lot and EUR 5 of the second: cost EUR 12. If actual net
proceeds are EUR 27, the realized gain is EUR 15; 2 items remain at cost EUR 10.

Amounts use Decimal with half-up cent rounding. Purchase totals and fees are
rounded to cents. A partial disposal receives its proportional remaining lot
cost rounded to cents; the last portion gets the residual cents. Three sequential
one-unit disposals of a EUR 1 lot of 3 allocate EUR 0.33, 0.34 and 0.33, totaling
exactly EUR 1. Market value rounds the quantity times the unrounded unit price.

A supplied `net_amount` establishes the acquisition cost or sale proceeds. Without
it, a gross amount (or quantity times unit price) **and explicit fees** are needed.
Missing fees are not assumed zero. Zero fees must be recorded as zero. The journal
validator checks consistency where net, gross and fee fields are all present.

## Movement types and chronological limits

- Purchases create lots with their known net acquisition cost, otherwise unknown.
- Free drops create zero-cost lots; their zero cost does not make ROI defined.
- Positive adjustments and unmatched incoming transfers create unknown-cost lots.
- Negative adjustments and outgoing transfers consume FIFO lots without creating
  a sale or realized gain. They are not silently treated as sales.
- Explicit internal transfer pairs retain the original lot cost and acquisition
  order. They are not new purchases and do not create a gain.

Optional private `transfer_links.csv` supplies `out_id,in_id` transaction IDs.
Each ID can be linked once. Both must refer to the same item and full quantity,
with a dated outflow strictly before the inflow. The first version requires exact
full-quantity pairs: split transfer links must be represented as separate actual
movements. Unlinked incoming transfers never inherit an assumed cost or guessed
source. External transfer costs remain unavailable. Holdings temporarily outside
the tracked portfolio are excluded until their linked return.

Unknown opening quantities, unimported opening categories, undated transactions
and multiple same-item movements at an identical timestamp make FIFO unavailable
for that item. Transaction IDs are not used to invent an order for simultaneous
movements. Supply real distinct timestamps when known; do not fabricate them.
Outflows exceeding available quantity and invalid transfer links raise errors.

## Tables, coverage and interpretation

- `sales` shows net proceeds, consumed cost, realized gain and ROI per sale.
- `items` shows remaining ledger quantity/cost, known cost subtotal/quantity,
  gross market value, gross latent gain and separate estimated net figures.
- `summary` reconciles categories and the global portfolio, with known subtotals,
  complete amounts, cost-quantity coverage and total/known sale counts.

Missing cost or price makes the corresponding complete amount `N/A`; known
subtotals remain separately labeled. Empty imported categories contribute zero;
unimported categories make global complete amounts unavailable.
An unimported opening category also leaves its complete realized gain unavailable,
even if it is empty and imported today: its past cost history was not observed.
Current empty holdings can still have zero remaining cost. A quantity mismatch
against observed inventory suppresses the item's current value/cost/latent gain
and marks its status. Historically computed sales remain independently reported.
Coverage counts units with known remaining cost, not their unknowable market weight.

`unrealized_gain` is **gross market value minus remaining acquisition cost**.
`--estimated-sell-fee-rate` is an optional fraction in [0,1]. It adds estimated
net sale proceeds and net latent gain, rounded per item. No default sale fee is
assumed; these estimates are unavailable without an explicit rate. It does not
change actual realized sale fees in the transaction journal. Global estimated
values sum the same item estimates rather than applying a separate rounding pass.

ROI uses a known positive acquisition-cost basis; it is unavailable for zero or
unknown cost. Neither portfolio quantity changes nor transfers are returns. The
report does not perform currency conversion or estimate taxes, execution delays,
liquidity or sale prices beyond the latest saved market observation.

All files stay under ignored `data/`. The tests use synthetic EUR examples,
including unknown costs, FIFO partial sales, fees, drops, linked transfers,
adjustments, missing/ambiguous dates, opening inventory, reconciliation, aggregate
coverage, future exclusions and source-file immutability.
