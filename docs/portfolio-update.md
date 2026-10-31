# Complete portfolio update

Run from the repository root with the project's Python environment:

```powershell
python src/update_portfolio.py school
python src/update_portfolio.py home
python src/update_portfolio.py home --root D:/Git/CKIN2 --at "2026-10-31 18:00:00"
```

`--root` selects the project containing `data/processed`; it defaults to this
repository. Existing conversion/import commands must have created the inventories.
`home` requires the reviewed `market_catalog.csv` with exact Steam listings.
No mapping is guessed by this command. `school` needs no catalog unless one exists.

The command validates inventories, prices, catalog (when present/required), and
existing global snapshots before making requests or writing data. It then:

1. Collects market observations in `home`, or reuses saved prices in `school`.
2. Saves the global monthly inventory snapshot in `home` only.
3. Prints current valuation, price timestamps/ages and historical valuations,
   with per-category and global coverage.

Without `--at`, collection uses its actual start time and the snapshot/report use
the local time after collection. `--at` overrides these times for reproducible
runs; it is not a way to reconstruct past holdings or market observations. Use
the same override when retrying an interrupted deterministic run. Timestamps are
local and timezone-naive, consistent with existing CSVs.

Exit codes: `0` complete success; `1` partial result (failed requests, missing
prices/quantities, or categories not imported); `2` failed stage. Old prices can
still produce a complete valuation after a failed request, but the run remains
partial. Dates and price ages are printed so old observations remain visible.
Partial totals are displayed as `N/A`, separately from the known value.

## How snapshots work

A snapshot records **quantities at one moment**, not prices or transactions.
For example, September can contain 2 Recoil cases, while October contains 5.
September is valued with its own 2 cases and the latest prices available at or
before its snapshot time; October uses 5 and its own eligible prices. The change
in value combines quantity and price changes, so it is not an investment return.

`data/processed/global_inventory_history.csv` contains one snapshot per calendar
month. Running `home` again in October **replaces October**, while retaining
September and other months. This is the latest observation in the month, not a
guaranteed month-end balance. Missed months are not reconstructed.

Each of the six categories has an explicit state:

- `holdings`: item identities and quantities, which may be unknown.
- `empty`: the category was imported and contains no items; its value is zero.
- `not_imported`: the category has not been imported; its value is unavailable
  and the global total cannot be complete.

An empty category is different from a month without a snapshot. Unknown
quantities or missing historical prices remain unavailable rather than zero.
Historical valuation never borrows a price from a later date. `school` can read
existing snapshots but never creates one.

## Persistence and recovery

Market observations and global snapshot history are each replaced atomically.
The workflow is **not a transaction spanning both files**: if the snapshot fails,
successfully collected prices remain saved. Fix the reported error and rerun.
At the same explicit timestamp, observations replace matching item/source rows;
the monthly snapshot replaces that month's snapshot. With the real clock, a
later run intentionally adds a new dated market observation.

A reporting failure also retains successful prior writes. Invalid inputs stop
before network calls or data changes. `school` never writes data or requests
Steam. This command does not install a scheduled task, introduce retry policies,
or send notifications; scheduling is tracked separately in #34.

All CSVs remain private local data and are excluded from Git. Tests use temporary
synthetic files and simulated Steam responses.
