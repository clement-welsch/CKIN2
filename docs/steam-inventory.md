# Assisted Steam inventory import (#38)

CKIN2 tracks **one consolidated portfolio**, regardless of how many Steam
accounts provide observations. An account identifies a capture source, not a
separate portfolio or an additional quantity to add to the existing total.

The adapter reads local JSON exports. It does not log into Steam, download an
inventory or acquire storage contents. Public unauthenticated collection needs
public inventory visibility. Valve confirms that objects inside storage units
are absent from Steam Community Inventory until retrieved:
[inventory privacy](https://help.steampowered.com/en/faqs/view/46A2-2B3C-95CC-8878),
[storage units](https://help.steampowered.com/en/faqs/view/52CE-419B-6C8D-2E50).

## Pagination completeness versus portfolio coverage

`complete: true` means **all pages of the supplied inventory view** are present.
It does not certify storage coverage or the owner's entire wealth. Each schema-1
account export has two coverage fields:

| Field | Default | Supported values |
| --- | --- | --- |
| `inventory_scope` | `visible` | `visible`, `full_portfolio` |
| `source` | `steam_community` | `steam_community`, `owner_export` |

Legacy exports without these fields now default to visible observations. A
`steam_community` source cannot declare `full_portfolio`. That scope requires an
explicit `owner_export`: the owner attests that the supplied inventory includes
all relevant items, including storage contents. CKIN2 validates its structure,
not the truth of that declaration. Renaming a public export's fields does not
retrieve its missing contents.

## Visible observations: preserve the known portfolio

```json
{"schema":1,"account_id":"main","collected_at":"2026-11-09T18:00:00",
 "complete":true,"inventory_scope":"visible","source":"steam_community",
 "pages":[{"success":1,"more_items":0,"assets":[],"descriptions":[]}]}
```

This is a fully paginated, empty **visible view**, not an empty portfolio.
The preview reports `action: record_visible_observation`, source coverage,
per-account quantities, `observed_holdings` and `observation_differences`:

- `not_observed`: a known item was not in the view; visible quantity stays null.
- `visible_below_known`, `visible_matches_known`, `visible_exceeds_known`:
  observations compared with the known global quantity.
- `newly_observed`: an observed item has no known portfolio row.
- `known_total_unknown`: the portfolio row exists but its total is unknown.

None of these statuses identifies a sale, acquisition, transfer or storage
location. Even a newly visible item is not automatically added: it may already
be part of the portfolio through another account or an unobserved storage unit.
Global `holdings`, imported category coverage and known/unknown quantities remain
unchanged. For example, five known cases and two publicly visible cases remain
five known cases; zero visible cases also leave the five intact. The difference
of three does not certify three stored cases.

After token approval in `home`, CKIN2 atomically writes the latest selected view
to ignored `data/processed/steam_inventory_visible.json`, with account dates,
sources, per-account details, matched quantities and unresolved listings.
Unmapped objects may be recorded as unresolved observations; they never become
invented portfolio identities. A content-addressed audit under `data/imports`
retains the reviewed plan, assets and previous observation before replacement.
An interrupted write leaves the prior observation and portfolio intact; an
unreferenced audit file may remain.

The latest view contains only its explicitly selected accounts. It never sums
cached observations from omitted accounts. Previous dates remain as freshness
guards, including for an account omitted in the latest view. Older captures are
rejected on application. Repeating the same current source and catalog mapping
is a no-op; a corrected mapping may resolve a previously unknown observation.

## Two weekly-drop accounts, one main inventory

For two accounts used to obtain weekly drops, CKIN2 retains one global portfolio.
If the items are consolidated on the main account, a visible capture of that
account is sufficient to observe its current public view. Optionally select both
accounts to see drops still on the secondary account. No primary-account
configuration or per-account portfolio duplication is needed.

To preview both accounts, use the existing local envelope:

```json
{"schema":2,"complete":true,"accounts":["replace with schema-1 account objects"]}
```

Each element is an object, not a filename. Put `inventory_scope` and `source` on
**each account export**, not the outer envelope. All accounts must have the same
inventory scope; mixed visible/full selections fail. Duplicate accounts and
partial page chains fail. Include empty accounts explicitly when describing
their visible state. Account-scoped asset deduplication and exact listing
matching precede aggregation. Per-account details retain capture dates, unique
asset counts, matched/unresolved quantities and matched item quantities.

Captures are not atomic across accounts. A transferred object can appear in the
secondary account's earlier capture and the main account's later capture, with a
changed asset ID. CKIN2 cannot prove that continuity from a public export. Capture
accounts consistently, avoiding transfers between captures. Observed sums remain
observations and are never added to the existing portfolio. Importing main alone
after a two-account observation neither deletes secondary holdings nor adds its
cached quantities a second time. Weekly-drop eligibility or delivery is not
inferred from these captures.

## Explicit full-portfolio replacement

For a reviewed, complete owner export, set both fields on every account:

```json
{"inventory_scope":"full_portfolio","source":"owner_export"}
```

This snippet supplements the required schema-1 envelope and pages. Such an export
must actually contain storage contents and the complete intended account scope.
Use the main account alone only if it contains the full holdings being declared;
include the secondary account if relevant items are still there. The preview
reports `action: replace_portfolio`, old/new quantities and deltas. Missing items
may become zero **only in this explicit full-portfolio replacement**. All exact
listings must resolve against reviewed `market_catalog.csv`; unknown or ambiguous
listings block application. All six supported categories are declared covered.

After token approval, the importer atomically replaces
`data/processed/steam_inventory_override.json`. Shared `load_holdings`, reports
and snapshots consume that single consolidated total. The legacy inventory CSVs
and purchase costs remain untouched. A content-addressed backup preserves the
previous override, prior effective holdings and reviewed asset trace.
`--restore` reverts only the last portfolio override; visible observations remain
separate and do not affect the restored holdings. No transaction, acquisition
date or purchase price is inferred.

Existing overrides require the same account set and nondecreasing capture dates
per account. Restore the previous override before deliberately changing its
account scope. These replacement restrictions do not prevent observing just the
main account. Identical source/current quantities remain idempotent.

Overrides created before this correction remain readable and restorable. Their
coverage cannot be established retrospectively; the preview identifies them as
`portfolio_basis: legacy_override_coverage_unverified`. Review their backup and
source before relying on the quantities. The fix does not reconstruct items
already erased by a previous import. Other basis labels are `manual_csv` and
`owner_declared_full_portfolio`; none authenticates actual storage contents.

## Commands and validation

```powershell
python src/steam_inventory.py school --export data/imports/export.json --catalog data/processed/market_catalog.csv
python src/steam_inventory.py home --export data/imports/export.json --catalog data/processed/market_catalog.csv --apply-token REVIEW_TOKEN
python src/steam_inventory.py home --restore
```

The same CLI selects observation or replacement from the export's coverage.
The review token binds coverage, provenance, accounts, observations and the
current portfolio. Editing them requires a new preview. `school` never writes,
including locks. Test `home` runs use temporary synthetic fixtures only. The old
category-only notebooks continue reading legacy CSVs rather than the override.

Schema-1 exports require `schema: 1`, `account_id` (nonblank string),
`collected_at` (local naive ISO timestamp), `complete: true`, `pages: [...]`.
Pages require integer `success: 1`, lists `assets`/`descriptions`, integer
`more_items: 0|1`. The first page has no `start_assetid`; subsequent pages must
match the previous `last_assetid`. The last page requires `more_items: 0`.
Empty inventories still supply empty lists. Asset `assetid`, `classid`,
`instanceid` and `amount` are explicit ASCII digit strings; amounts are positive,
appid is 730 and contextid is 2. Descriptions require matching appid/classid/
instanceid and exact `market_hash_name`. Identical repeated assets count once;
conflicting duplicates, missing descriptions, malformed pages and cursor cycles
fail before any preview is produced. No remote coverage guarantee follows from
valid pagination.
