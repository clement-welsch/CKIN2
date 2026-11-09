# Local dashboard (#37)

```powershell
python src/dashboard.py
```

Open http://127.0.0.1:8765. Optional `--root PATH` selects a data directory and
`--port 8766` changes the loopback port. No public binding, CDN, remote font,
collection, file export or data mutation occurs on page load. Stop with Ctrl+C.
Each GET reloads local data without caching; input errors produce a reset link.
Do not expose the server through a proxy or port forwarding.

Views cover current value, six categories, object details, historical values,
fixed-basket price indices, transactions, FIFO results, experimental forecasts
and archived forecasts. Costs/history/forecasts missing from local files remain
explicitly unavailable. Shared analysis, snapshot, prediction and FIFO functions
perform the calculations. Coverage, missing categories, price age and source
provenance appear next to the values. Latest used price and snapshot are shown.

Category and object filters define a selected portfolio, with explicit empty
markers for excluded categories. Period start filters history/charts and known
transaction dates; undated transactions remain visible. End includes that day.
An earlier end uses the latest historical snapshot, **never today's quantities
in the past**. No snapshot means historical value is unavailable. Current
holdings and historical inventory may differ: the fixed-basket index and
experimental forecast explicitly use the currently selected cohort. Historical
value uses actual quantities of each snapshot. Training includes the past
before the visible window and excludes dates after the end. FIFO is cumulative
from the opening inventory, as labeled. Archive baskets are never relabeled as
object forecasts and are hidden under an object filter.

Tables scroll horizontally on narrow screens. Charts resize and preserve gaps;
missing full totals are never connected across incomplete snapshots. The
dashboard is French; repository interfaces/documentation remain English.

## Notebook consistency (#78)

The dashboard and category notebooks share snapshot selection and valuation.
See [the notebook contract](category-notebooks.md#shared-portfolio-contract-78)
for data-root, analysis-clock and current/historical scope controls. Quantity
provenance distinguishes manual CSVs, owner-declared full replacements, unverified
legacy overrides and historical snapshots. Unknown CSV capture dates remain
unknown. Cached visible Steam observations are never added to portfolio holdings.

## Forecast diagnostics (#55)

The forecasts view plots actual/predicted fixed-basket indices and common-window
MAE/RMSE, separately for baseline and model samples. It displays origin, target,
training end/count, monthly age and shared insufficient-history diagnostics.
The horizon is one month; no confidence interval is inferred. Period start
filters evaluated targets after past-only model fitting, including metric
recalculation on the visible targets. Category filtering applies to every table.
Archive metrics remain grouped by issued/retrospective kind, frozen basket,
revision, code and settings. Unemitted records are hidden at historical cutoffs;
pending/unavailable targets never contribute to scores. Item filters hide
category archives and their metrics. Viewing never issues or saves a forecast.

## Community research (#56)

The Research view reuses the local `research()` workflow. It shows channel
verification, video availability/provenance, exact/family/ambiguous mentions,
annotation availability, creator arguments and separately verified facts.
Canonical evidence links retain imported subtitle offsets; TXT has no invented
offset. No transcript text is rendered. External links require an explicit click.
Signals are bounded by publication and collection dates; future annotations are
masked. Object/category filters select mentions and experiments, while video
coverage explicitly remains corpus-wide. Period start filters publications for
mentions and target dates for backtests after training. Common-window errors
are recomputed for the displayed targets. There is no network call, corpus
acquisition or file write on page load. Empty/partial data, unverified channels
and unproven predictive utility remain explicit; #40 remains experimental.

## Performance details (#54)

The performance view reuses `explain_changes` for item-level price/quantity
contributions. Period start selects interval end dates while retaining the
preceding snapshot. Category and exact-item filters apply before calculation.
Charts sum only covered contributions; the detailed table retains unavailable
rows, so a covered subtotal is never presented as a complete portfolio change.
FIFO item results and realized sales are cumulative through the selected end,
independent of period start. Net proceeds include recorded sale fees; unknown
costs and reconciliation failures remain unavailable. No future fee is inferred.

## Compact portfolio summary (#80)

The landing page presents shared total/known values, held distinct identities,
quantity/price coverage, missing categories and old prices. Zero positions do not
count as holdings; unknown quantities remain visible. Prices older than 45 days
at the analysis cutoff are labeled old without silently dropping their known
valuation. Quantity provenance/date, price date range and recorded snapshot date
are separate. Historical selection never reuses current quantities. Legacy
owner overrides remain labeled unverified. Detailed tables remain in category
and exact-object views rather than the landing page.

## Known versus visible Steam inventory (#81)

The reconciliation page reads only `steam_inventory_visible.json`'s latest
explicit account selection, validates per-account dates/identities and aggregate
quantities, and compares it with the selected known portfolio. Choose all selected
accounts or one account; omitted cached accounts never contribute quantities.
Missing visible rows stay unknown, including empty captures and stored items.
Dates, source, unresolved mappings and omitted accounts remain visible. Capture
skew and transfer risks are explained without inferring a transfer, sale or
storage location. Future captures are unavailable in historical views; audit
files are not silently replayed. The page never applies adjustments or collects.
