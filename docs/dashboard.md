# Local dashboard (#37)

The **Copier l’inventaire dans le cloud** button publishes saved inventory and
history through the configured cloud connection. It runs in the background and
shows its result without changing filters or collecting Steam prices. Repeated
clicks cannot start overlapping dashboard publications; the writer lock also
prevents overlap with inventory collection. Page loads only read status. See
[cloud setup](cloud-inventory.md) to connect Google or a synced folder first.

```powershell
python src/dashboard.py
```

Open http://127.0.0.1:8765. Optional `--root PATH` selects a data directory and
`--port 8766` changes the loopback port. No public binding, CDN, remote font,
collection, file export or data mutation occurs on page load. Stop with Ctrl+C.
Each GET reloads local data without caching; input errors produce a reset link.
Do not expose the server through a proxy or port forwarding.

## Steam price refresh

Click **Mettre à jour les prix Steam** to run the existing `update_portfolio.py
home` workflow in the background against the dashboard's data root. It collects
the entire portfolio (independent of displayed filters), writes successful price
observations and replaces the current monthly global snapshot. Page loads alone
remain read-only. The dashboard stays available during collection and reloads
the current page when it finishes, preserving filters. Historical date filters
still select historical prices.

The status reports success, partial coverage or failure, with expandable command
output. Failed observations retain valid older prices. Repeated clicks cannot
start another dashboard collection while one is running; the existing process
lock also prevents overlap with scheduled or terminal collection. Refresh uses
a same-origin POST; GET requests never initiate collection. Restart an already
running dashboard after updating the code to see the new button.

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

## Visible inventory reconciliation (#81)

The [visible-inventory reconciliation page](dashboard-reconciliation.md) at
`/reconciliation` compares current known quantities with the selected local
account capture. It remains read-only and independent of optional price files.

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

## Held inventory table (#82)

The Inventory view lists positive or unknown owned quantities only, keeping exact
variant names and exact-identity detail links. Literal case-insensitive search,
category/object filters, known/unknown quantities and recent/old/missing prices
combine before stable sorting (missing values last) and pagination. Page sizes
are 10/25/50/100; out-of-range pages clamp to the last page. Shared snapshot
valuation computes totals for the entire filtered selection, independent of the
page. Missing category coverage remains explicit; unknown amounts never become
zero. Controls and pagination use ordinary keyboard-accessible forms and links.

## Data-quality centre and invalid datasets (#85)

The Quality view shares held-row price/quantity statuses with the landing page
and inventory. It groups unknown quantities, missing/old/invalid prices,
unimported categories, unverified legacy replacements and unresolved visible
Steam mappings. Every diagnostic includes its affected scope, impact and a
manual correction procedure. It never resets quantities, repairs files or
collects prices. The landing page links to these diagnostics; its filters fold
away initially to keep the current summary visible on mobile.

The latest valid-by-schema local scheduled result is selected by its recorded
end timestamp (UTC comparison), not filename or mtime. Success, partial result,
failure and no history are distinct. A malformed runtime record makes that
history unverifiable instead of claiming an earlier success. Future records
are not displayed at an earlier analysis cutoff. Collector stale counts retain
the collector's own policy; they are not relabeled as dashboard selection counts.
Unscheduled commands without persisted run records cannot supply this history.

Dashboard reads isolate rejected datasets: invalid snapshots block historical
selection but leave current quantities available; invalid archives, metadata,
corpora, visible captures, transactions or FIFO inputs block their dependent
components. Rejected portfolio prices never become fallback/zero valuations.
Missing quantities stay unavailable when inventory validation fails. Explicit
market observations do not depend on an optional catalog unless legacy others
price classification requires it. A visible error identifies the rejected dataset
and links to correction procedures. Core `analyze()` and notebooks remain strict
by default; the dashboard opts into diagnosed partial reads and retains the
same underlying validators. No invalid rows are silently accepted or rewritten.

Combined verification: 207 synthetic tests on Linux CPython 3.12.14, dependency
compatibility and whitespace checks passed. Chromium desktop and 390px mobile
checks exercised summary, inventory paging/search/filter, exact identity links,
account selection, quality results and keyboard focus. No page errors, document
horizontal overflow, external network requests or fixture-byte changes occurred.
Screenshots contain synthetic data only. Remote CI validates the supported
Python version on Windows and Linux for the published review branches.

## Reading reports, snapshot comparison and favorites

The [two-snapshot comparison](snapshot-comparison.md) selects exact recorded
states and retains covered effects, exclusions and unavailable residuals.
[Navigation and browser favorites](dashboard-navigation.md) preserve compatible
URL filters, show resets, resolve preset/custom periods and save preferences
only in the browser. The independent `/reconciliation` route remains available;
the integrated Rapprochement view additionally supports scoped/historical cutoffs.

The seven [notebook reading reports](notebook-reports.md) lead with summaries and
keep detailed checks in appendices. The [remaining-issue audit](remaining-issues-status.md)
separates delivered features, bounded real-source measurements and external
validation blockers. Item imagery has a documented [no-go decision](images-feasibility.md)
with no page-load image requests. Research shows its dated corpus prerequisites.
