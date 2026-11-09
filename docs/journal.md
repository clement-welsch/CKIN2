# Development journal

Entries record development and integration milestones in reverse chronological
order. Dates use Europe/Paris. Status statements describe the time of writing;
linked issues and pull requests remain the source for their current status.

For future feature work, add an English entry in the same PR with the development
date, feature summary, branch, tracking issue/PR, validation performed and material
limitations. Clearly distinguish planned work, work in review and merged changes.
Keep personal inventory data, credentials and private notebook outputs out of
the journal.

## 2026-11-09 - Dashboard forecast diagnostics (local review)

Branch: `codex/dashboard-forecasts`. Tracking: #55.

Review: [#65](https://github.com/clement-welsch/CKIN2/pull/65), stacked on
[#64](https://github.com/clement-welsch/CKIN2/pull/64) (#54) to resolve shared
dashboard fields before integration. Final combined suite: **157 tests passed**;
whitespace checks passed. Visual browser checks remain unperformed.

- Added predicted/actual plots and common-window MAE/RMSE using shared past-only
  experiments. Period start filters targets after training, then recomputes scores.
- Exposed monthly freshness, training details and immutable archive metrics,
  preserving original grouping and hiding category archives under item filters.
- Validation: two focused synthetic tests passed for shared-calculation parity,
  empty/short history, zero targets, period/category/item filters, archive metrics,
  future-data exclusion and unchanged files. No Steam call or forecast issuance.

## 2026-11-09 - Dashboard performance details (local review)

Branch: `codex/dashboard-performance`. Tracking: #54.

- Exposed shared price/quantity contributions with period and identity filters,
  preserving the preceding snapshot and explicit incomplete coverage.
- Added cumulative FIFO sale details with recorded net proceeds and cost limits.
- Validation: two focused synthetic tests passed, including shared-calculation
  parity, period boundaries, empty data and unchanged fixture files. Initial
  baseline: 153 tests passed. No Steam access or personal data writes.

## 2026-11-09 - Steam history study preparation (in review)

Branch: `codex/steam-history-study`. Relates to #57; does not close it.

- Added an offline, read-only analyzer for one sanitized capture and a wholly
  synthetic sample. Explicit UTC offsets, exact identities, finite prices,
  integer volumes, duplicate/future timestamps and empty responses are checked.
- Documented a bounded manual home-network study: observed authentication,
  graph parity, currency/time/measure, source access/reuse and go/no-go evidence.
- All 160 branch tests, three focused study tests and the sample CLI passed;
  whitespace checks passed. No network access or data writes were performed.
  Real Steam access/schema/terms remain unverified; verdict pending.
  #58 must await a positive live study. No historical data are imported.

## 2026-11-04 - Detailed dashboard item view (in review)

Branch: `codex/dashboard-item-detail`. Tracking: #53. Depends on #52/#51.

- Added literal-name search and exact variant selection across held, historical,
  priced, local-catalog and eligible release identities, including unowned items.
- Reused shared price charts/indices, reference separation and snapshot valuation.
  Watchlist observations supplement item detail without inventing held quantities.
- Displayed declared purchase metadata separately from FIFO costs/gains; unknown
  basis and missing market data stay unavailable. Added an empty-provenance merge
  correction for acquisition-only histories exposed by the regression tests.

Validation: all 153 combined synthetic tests passed. Browser checks covered the
category view, exact unowned variant, market/reference charts, source attribution
and the 390px layout. A confirmed FIFO opening cost was checked separately from
the declared CSV unit price. `git diff --check` passed. No personal notebook,
inventory, credential or CSV is modified.

## 2026-11-04 - Category dashboard views (in review)

Branch: `codex/dashboard-category-views`. Tracking: #52. Depends on #51.

- Added explicit dashboard navigation and separate category pages for all six
  categories, including individual market series, coverage, value contributions
  and clearly separated acquisition references.
- Shared category price normalization/base-100 preparation with notebooks and
  reused their Plotly figures. Model training is limited to the forecasts view.
- Preserved local read-only loading, period/categorization semantics and source
  attribution. Detailed object and research UI remain separate feature work.

Validation: all 149 tests passed before the explicit-gap refinement; the three
targeted category tests then passed with missing observations preserved as chart
gaps. The final combined suite and browser checks follow with #53.
No personal notebook or CSV is changed.

## 2026-11-04 - ByMykel attribution and source register (in review)

Branch: `codex/bymykel-attribution`. Tracking: #51.

- Pinned the upstream MIT license review to commit
  b014e92bc37f4143ead2cb1af26aa85f2c3d6688 and retained its exact text/copyright.
- Added notices, an actual-use register and review guidance for changed sources
  or personal/public/hosted/commercial distribution. Valve assets remain outside
  the cleared scope; no upstream catalog, code or images are bundled.
- Added an offline dashboard source page showing attribution, full license and
  declared local release provenance without loading portfolio analysis.

Validation: all 147 synthetic tests passed, including source-page HTTP/render
checks and the existing dashboard suite. The retained license hash matches the
pinned upstream copy; `git diff --check` passed. No personal notebooks or CSVs
are changed.

## 2026-11-04 - Next-feature assessment and offline community research (in review)

Branch: `codex/community-signals`. Tracking: [#40](https://github.com/clement-welsch/CKIN2/issues/40).

- Assessed actual remote implementation and selected the four remaining open
  features: dashboard #37, assisted inventory import #38, independent market
  universe #39 and community research #40. See the
  [dated assessment](project-status-2026-11-04.md) for review links and limits.
- Added inert TXT/SRT/VTT imports, explicit verified-channel metadata,
  exact/family/ambiguous aliases, timestamped evidence links, annotation
  provenance and duplicate-content grouping. Unverified channels remain inert.
- Added monthly walk-forward price-only versus community-feature Ridge
  comparisons, common-window baselines/MAE/RMSE and explicit insufficient-history
  diagnostics. Future collection/annotations cannot enter historical features.
- Added a read-only research notebook and tests for absent/populated synthetic
  corpora, subtitle parsing, duplicate mentions, unknown matches, temporal
  availability and future-price exclusions.

Real channel verification, authorized corpus acquisition, annotation review and
empirical predictive benefit remain unverified. No live Steam/YouTube calls,
personal CSV writes, issued forecasts or full transcript publication occur.
Validation: full branch suite passed 143 tests, including 5 community tests and
complete notebook execution with absent and synthetic populated corpora.
After integrating the reviewed dashboard #49, all four features passed 145 tests
together. One preceding run hit a transient Windows access-denied error in an
existing scheduler test's temporary-file replacement; the unchanged full rerun
passed. `pip check`, notebook schema validation and `git diff --check` passed.

## 2026-11-03 - Immutable forecast archive and realized accuracy (in review)

Branch: `codex/forecast-archive`. Tracking: [#36](https://github.com/clement-welsch/CKIN2/issues/36).
Review: [PR #46](https://github.com/clement-welsch/CKIN2/pull/46), targeting `develop`; not merged.

- Added explicit one-month forecast issuance with frozen baskets/base prices,
  weights, information cutoff, model parameters, software/source hashes and
  available-data fingerprints. Real issues and retrospective simulations remain
  separate; changed inputs require an explicit revision without overwriting.
- Added read-only month-close evaluation with the archived freshness policy,
  pending/unavailable states, zero-target support and MAE/RMSE on common method
  windows. Revision, basket/base, code and settings groups are kept distinct.
- Added a read-only tracking section to the prediction notebook and documented
  atomic record publication, interrupted batches, private storage and limits of
  historical observation timestamps versus ingestion-time provenance.

Validation: all 132 tests passed, including 16 archive tests; CLI help, Python
compilation and `git diff --check` passed. Tests use synthetic issuance, immutable retries, revisions, changing baskets,
future exclusions, target coverage, model/baseline common windows and full notebook
execution. The review reference is recorded in the PR.
No live collection or private forecast issuance is performed during testing.

## 2026-11-03 - FIFO profit and loss report (in review)

Branch: `codex/fifo-profit-loss`. Tracking: [#35](https://github.com/clement-welsch/CKIN2/issues/35).
Review: [PR #45](https://github.com/clement-welsch/CKIN2/pull/45), targeting `develop`; not merged.

- Added a read-only EUR FIFO report for per-sale realized gains, remaining cost,
  gross/estimated-net latent gains and item/category/global coverage.
- Preserved unknown costs/fees, zero-cost drops, quantity reconciliation and
  unavailable ROI for zero or unknown bases. Decimal cent allocations preserve
  lot totals through partial sales.
- Added optional private opening costs and explicit full-quantity internal
  transfer links, retaining the original lot acquisition order on return.
- Documented simultaneous/undated movement ambiguity, partial aggregates and
  optional estimated sale fees without altering journal or inventory sources.

Validation: all 116 tests passed (including 18 FIFO tests); CLI help, Python
compilation and `git diff --check` passed. Tests use synthetic FIFO, fee, transfer,
opening, coverage and read-only fixtures; the review reference is recorded in the PR.
No tax treatment, currency conversion or live sale/price collection is included.

## 2026-11-03 - Optional scheduled collection and failure tracking (in review)

Branch: `codex/scheduled-collection`. Tracking: [#34](https://github.com/clement-welsch/CKIN2/issues/34).
Review: [PR #44](https://github.com/clement-welsch/CKIN2/pull/44), targeting `develop`; not merged.

- Added an opt-in home/school wrapper around the unified portfolio workflow,
  elapsed-UTC cadence, configurable timezone labels and a manual Windows task
  registration script. No scheduled task was registered during development.
- Shared a kernel process lock with manual unified home updates; process exit
  releases it without deleting the lock file or evicting a live owner.
- Reused the price parser with a bounded HTTPS retry adapter, classified errors,
  exponential backoff and seconds/HTTP-date Retry-After support. Long waits defer
  remaining listings and the next run rather than bypassing server cooldown.
- Added atomic private run events, last-success/next-due state, interrupted-run
  detection and condition-change-only console alerts, with no external connection.
- Documented shutdown/sleep/offline behavior, partial-file persistence, manual
  installation/removal and the difference between cadence and a fixed daily hour.

Validation: all 98 tests passed; CLI help, Python compilation, PowerShell script
syntax and `git diff --check` passed. Synthetic tests cover time, locking across process exit, retries,
deferral, privacy, invalid mappings, repeated-alert suppression and school
immutability. Full-suite and final validation results are recorded in the PR.
The registration script is syntax-checked only; no live Steam calls, private CSV
changes, notification connections or Task Scheduler installation were performed.

## 2026-11-01 - Reconcile portfolio update PR #43 with develop

Branch: `codex/portfolio-update-command`.
Review: [PR #43](https://github.com/clement-welsch/CKIN2/pull/43).

- Integrated the implementation already merged in PR #42, retaining its
  structured result, `--date` / `--snapshot-path` options, stale-price status,
  live per-item timestamps and rejection of backdated home collection.
- Retained the snapshot explanation as a focused guide linked from the main
  workflow documentation, removing incompatible `--at` examples.
- Added individual price dates/ages to the report, graceful failure for malformed
  inventory schemas and regressions for reporting failures after successful writes.

Validation: all 86 tests passed, CLI help and `git diff --check` passed.
No live Steam collection or private
CSV changes are required. The PR remains open for review.

## 2026-10-31 - One-command portfolio update

Branch: `codex/one-command-update`, based on the current `develop` branch.
Tracking: [issue #33](https://github.com/clement-welsch/CKIN2/issues/33),
[PR #42](https://github.com/clement-welsch/CKIN2/pull/42). Status: in review;
not merged when this entry was written.

- Added `update_portfolio.py` to validate processed inputs, collect prices,
  save a global monthly snapshot and print current/historical reports.
- Reused the existing collection, snapshot and valuation functions, adding
  explicit home/school modes, configurable data/history paths and an exact
  school-mode valuation cutoff. Home rejects backdated live-price execution.
- Added a collection clock so the unified home command timestamps individual
  observations when retrieved and takes its snapshot after collection.
- Distinguished exit statuses 0 (complete success), 1 (partial result, including
  stale/missing data or failed prices) and 2 (validation/processing failure).
  Stage summaries identify completed steps and the failing step.
- Preserved collected prices when snapshot writing fails; each CSV replacement
  remains atomic independently. Repeat runs do not corrupt history or duplicate
  identical item/source/timestamp observations. School never writes data or
  contacts Steam.
- Added synthetic regressions for full/partial collection, preflight failures,
  snapshot failure and retry, real timestamps and read-only CLI operation.
- Documented the command, date semantics, exit statuses and partial-write scope
  in [the workflow guide](one-command-update.md), linked from the README.

Environment verification used the recreated project `.venv`: CPython 3.14.6
matches `.python-version`, and `pip check` passed. All declared project imports
loaded successfully. Seven targeted workflow tests and the full suite of **83
tests** passed; `git diff --check` passed. Remote CI status is available in the PR.
No private CSVs were modified and no live Steam request was made during testing.
Scheduling, notifications, concurrency and request-batch resumption remain outside
this issue.

## 2026-10-31 - Global portfolio tracking and experimental forecasting

The following pull requests were reviewed and merged into `develop` on
2026-10-31. Implementation, tests and documentation were split into multiple
commits per feature.

| Feature | Issue | Pull request | Development branch |
| --- | --- | --- | --- |
| Multi-category market price collection | [#23](https://github.com/clement-welsch/CKIN2/issues/23) | [#28](https://github.com/clement-welsch/CKIN2/pull/28) | `codex/multicategory-prices` |
| Global monthly inventory snapshots | [#24](https://github.com/clement-welsch/CKIN2/issues/24) | [#29](https://github.com/clement-welsch/CKIN2/pull/29) | `codex/global-snapshots` |
| Transaction journal and reconciliation | [#25](https://github.com/clement-welsch/CKIN2/issues/25) | [#30](https://github.com/clement-welsch/CKIN2/pull/30) | `codex/transaction-journal` |
| Global portfolio analysis notebook | [#26](https://github.com/clement-welsch/CKIN2/issues/26) | [#31](https://github.com/clement-welsch/CKIN2/pull/31) | `codex/global-analysis` |
| Experimental prediction notebook | [#27](https://github.com/clement-welsch/CKIN2/issues/27) | [#32](https://github.com/clement-welsch/CKIN2/pull/32) | `codex/experimental-prediction` |

### Market data and inventory history

- Added shared, stable category/item identities and a private catalog containing
  exact Steam listing names for cases, skins, souvenirs, stickers, charms and
  agents. Historical identities remain available after an item leaves holdings.
- Added `update_market_prices.py`, preserving legacy exports and recording fresh
  timestamped EUR observations separately. Failed collections retain previous
  observations; reports show coverage and freshness. School mode stays read-only.
- Added `global_snapshots.py` with atomic monthly replacement, actual snapshot
  timestamps, explicit empty/unimported category states and unknown quantities.
  Valuation uses each snapshot's holdings and only prices known at that instant.

### Transactions and global analysis

- Added `transactions.py` for purchases, sales, drops, transfers and adjustments,
  an explicit opening inventory, idempotent batch imports and reconciliation.
  Unknown dates and costs remain unknown; mismatches never rewrite holdings.
- Added `global_book.ipynb` for global/category values, distribution, fixed-cohort
  price comparisons and covered price/quantity contributions. Stickers, charms
  and agents are displayed separately. Price provenance and missing data remain
  visible, and unavailable comparisons are not filled with invented values.

### Prediction experiment

- Added `prediction_book.ipynb` with monthly data audits, persistence and trend
  baselines, and a first Ridge model with past-only preprocessing/training.
- Compared methods on common chronological evaluation windows using MAE/RMSE.
  Excluded the current month, acquisition references and estimated observation
  dates. Missing or stale monthly data remains unavailable.
- Started model fitting at 12 usable past training pairs, explicitly treating
  this as a technical threshold rather than proof of forecasting quality.

Validation: combined local integration passed **76 synthetic tests** on CPython
3.12.14 with the declared direct dependency versions. `pip check`, notebook
format validation and `git diff --check` passed. All authored code cells in both
new notebooks executed on complete/long, partial/short and empty fixtures; seven
Plotly figures were serialized across their complete fixtures. CSV bytes stayed
unchanged and committed notebooks contain no saved outputs. Future-target
perturbation tests verified that earlier predictions do not change.

Limits: these checks do not verify live Steam availability, manually supplied
listing mappings, browser pixel rendering or forecasting accuracy on private
data. No personal CSVs were committed. See the linked PR checks for remote CI
results on the repository's supported Python version.

Related integration: [PR #22](https://github.com/clement-welsch/CKIN2/pull/22),
also merged on 2026-10-31, corrected duplicate market observations in category
analysis and preserved decimal-zero acquisition markers during conversion.

Implementation notes: [collection](multicategory-prices.md),
[snapshots](global-snapshots.md), [transactions](transactions.md),
[global analysis](global-analysis.md), [prediction](prediction.md).

### Next backlog - planned, not implemented

The next selection is tracked separately from delivered features:

- P1: [one-command portfolio update (#33)](https://github.com/clement-welsch/CKIN2/issues/33),
  [scheduled collection and failure tracking (#34)](https://github.com/clement-welsch/CKIN2/issues/34),
  and [gains/losses after fees (#35)](https://github.com/clement-welsch/CKIN2/issues/35).
- P2: [forecast archiving and real-world evaluation (#36)](https://github.com/clement-welsch/CKIN2/issues/36),
  [interactive dashboard (#37)](https://github.com/clement-welsch/CKIN2/issues/37),
  and [assisted Steam inventory import (#38)](https://github.com/clement-welsch/CKIN2/issues/38).
- P2 research: [market-wide catalog and price series (#39)](https://github.com/clement-welsch/CKIN2/issues/39)
  and [community video trend signals (#40)](https://github.com/clement-welsch/CKIN2/issues/40).
  The initial creator selection is MasterShiny CS2, rubyjetski, IAMJERM - CS2,
  TDM_Heyzeus and LeChineur. Exact channel identities and transcript acquisition
  methods still need validation; no video collection has been implemented.

## 2026-10-29 - Historical valuation and market-data reliability

- [PR #19](https://github.com/clement-welsch/CKIN2/pull/19), tracking
  [#9](https://github.com/clement-welsch/CKIN2/issues/9), made zero-base notebook
  indices and performance indicators unavailable with explanations, while
  retaining valid zero prices for valuation.
- [PR #20](https://github.com/clement-welsch/CKIN2/pull/20), tracking
  [#10](https://github.com/clement-welsch/CKIN2/issues/10), added simulated Steam
  response/persistence coverage and rejected malformed prices without inventing
  observations or losing existing history.
- [PR #21](https://github.com/clement-welsch/CKIN2/pull/21), tracking
  [#12](https://github.com/clement-welsch/CKIN2/issues/12), shared detailed
  historical valuation and coverage between reports and the cases notebook,
  preserving per-snapshot quantities and backward-only price matching.

These three PRs were merged on 2026-10-29. Their original validation details and
scope limitations are recorded in the linked PRs and their dedicated documents.

## 2026-10-28 - Python environment and CI

Branch: `codex/reproducible-python-ci` (based on the category-notebooks commit).
Tracking: #11.

- Recorded CPython 3.14.6 in `.python-version` and clarified the scope of the
  direct dependency pins; transitive dependencies are not fully locked.
- Added GitHub Actions jobs for Windows and Linux on pushes, pull requests and
  manual dispatch. Jobs install dependencies, check compatibility and notebook
  imports, then run the synthetic unittest suite without personal CSVs or Steam.
- Documented setup and fresh-install verification in an ignored `.venv-ci`
  without replacing the working project environment.

Validation: the existing environment passed 36 tests. A fresh Windows CPython
3.14.6 environment installed all requirements, passed `pip check` and notebook
dependency imports, and passed the same 36 tests. `git diff --check` passed.
Remote Actions execution, including Linux installation, remains unverified
until publication and the first successful workflow run. No private data was
used or modified by this work.

## 2026-10-28 - Category notebooks

Branch: `Klement/feat/category-notebooks`.

- Replaced the single notebook entry point with dedicated cases, skins,
  souvenirs and others notebooks.
- Added reproducible conversion of raw spreadsheet exports into category
  inventories and market histories, preserving existing case files.
- Preserved manual acquisition reference rows across repeated conversions.
- Separated acquisition references from market indices and valuation; added
  acquisition markers, timelines and estimated-date hover details.
- Added regression tests and documented missing-data and purchase-cost limits.
- Declared the dependency versions used in the working Python 3.14.6 environment.
- Cleared saved notebook results before publication to protect local data.

Validation: 36 tests passed during the latest functional verification; all four
notebooks executed successfully and generated 16 figures without changing CSVs.
Fresh-environment installation and automated CI remain follow-up work in #11.

Local inventory corrections stay outside Git. No private quantities, acquisition
dates or prices are recorded in this journal.

Tracking: [#16](https://github.com/clement-welsch/CKIN2/issues/16) covers
category conversion and notebooks. [#11](https://github.com/clement-welsch/CKIN2/issues/11)
remains open for dependencies, fresh-environment installation and CI.
