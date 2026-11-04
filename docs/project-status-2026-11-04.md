# Project assessment — 2026-11-04

## Established baseline

The initial local checkout was on `Klement/fix/category-price-integrity` at
`8cfc403`, with a clean working tree. Remote `develop` had progressed to
`91c7a35` (forecast archive #46). No project `AGENTS.md` was found in the tracked
tree; the conversation's user instructions apply. All feature work targets
`develop`, uses separate review branches and preserves private CSV files.

Existing delivered modules cover CSV conversion, category notebooks, observed
market-price collection, global monthly snapshots, transaction validation and
reconciliation, global fixed-basket analysis, experimental price prediction,
one-command updates, opt-in scheduling/retries, FIFO gains/losses, and immutable
forecast archives with realized-error evaluation. The README's original V1
checklist is historical and understates this implemented scope.

The first 132-test execution failed with 18 dependency errors because the old
`.venv-ci` lacked declared scikit-learn. Installing the existing pinned
requirements resolved those inherited errors. This was environment repair,
not a change to the dependency contract. No live price collection was needed.

## Selected next four features

| Issue | Delivery | Review | Material limit |
|---|---|---|---|
| #39 | Independent versioned market universe, explicit watchlist, request budget and fixed-cohort indices | [#47](https://github.com/clement-welsch/CKIN2/pull/47), integrated during this session | Reviewed local catalog releases; no measured market-wide coverage or automatic raw-source expansion |
| #38 | Complete local Steam export preview, exact matching, token-bound apply and restorable atomic override | [#48](https://github.com/clement-welsch/CKIN2/pull/48), integrated during this session | One account per override; no login/live API; old category notebooks keep reading their original CSVs |
| #37 | Local read-only dashboard with shared calculations and filters | [#49](https://github.com/clement-welsch/CKIN2/pull/49), integrated during this session | Historical value requires recorded snapshots; model/cost availability depends on local data |
| #40 | Offline transcript import, evidence links, reviewed aliases/annotations and chronological comparative experiment | Separate `codex/community-signals` review | Real channel verification, authorized corpus acquisition and empirical benefit are still unverified |

No merge was executed by the implementation task. #47, #48 and #49 were merged
externally while work continued. A concurrent local switch to `develop` caused
the dashboard commit to be created there locally; it was then copied forward to
its dedicated branch and only that branch was pushed. No history was discarded.

## Validation and limits

After integrating #47 and #48, the dashboard's full run passed **140 tests**.
Desktop and 390px-wide browser checks used synthetic data, exercised category
filters and confirmed responsive controls/tables. Dashboard CI for commit
`9d3140c` completed successfully. Unit tests cover empty/partial data, unavailable
prices, import pagination and duplicates, idempotence, restore, write failure,
read-only mode, request budgets and historical membership cutoffs.

The community notebook is executed by tests with absent and synthetic populated
corpora. Tests check timestamped evidence, future annotation/collection
exclusion, same-origin metrics and past-only training. Synthetic experiments
validate mechanics, not economic predictive value. No real transcripts or
creator claims are published. No personal inventory report was exposed.
The final combined suite passed **145 tests**. A preceding combined run failed
once on Windows temporary-file access in an existing scheduler test; an unchanged
full rerun passed. `pip check`, notebook schema validation and diff checks passed.

Actual data operations stayed in `school` mode. Test-only `home` branches use
temporary synthetic files and mocked transport, not Steam.

## Recommended review focus

1. Confirm the import override convention is acceptable before using it with
   real quantities; shared global workflows and old category notebooks differ.
2. Review exact listing mappings and catalog provenance on a small selection
   before enabling collection. Measure coverage rather than claiming all CS2.
3. Validate dashboard filters on your local data in `school`; review unknown
   costs, incomplete categories and snapshot timestamps before interpreting totals.
4. Keep #40 experimental until channels, acquisition rights, annotations and a
   genuinely dated corpus allow an empirical common-window comparison.
