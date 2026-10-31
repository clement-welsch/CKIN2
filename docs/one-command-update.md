# One-command portfolio update (#33)

For a quantity-based example and the distinction between empty and unimported
categories, see [Understanding portfolio snapshots](portfolio-update.md).

From the repository root, using the project virtual environment:

```powershell
.\.venv\Scripts\python.exe src/update_portfolio.py home
.\.venv\Scripts\python.exe src/update_portfolio.py school
.\.venv\Scripts\python.exe src/update_portfolio.py school --date 2026-10-31T23:59:59
.\.venv\Scripts\python.exe src/update_portfolio.py home --root D:\Git\CKIN2 --snapshot-path D:\Git\CKIN2\data\processed\global_inventory_history.csv
```

The mode is explicit, independent of the weekday. Home collects live prices;
school performs the same read-only analysis with saved prices. `--root` selects
the directory containing `data/processed`. `--snapshot-path` optionally selects
the global history CSV (relative paths resolve from the current directory).
Input and legacy history paths cannot be used as the snapshot output.

## Execution order and dates

1. Validate inventories, all saved price inputs and any existing global history.
   At least one inventory file must be imported. Home also validates every
   current catalog mapping before any request or data write.
2. Collect prices using the existing collector. The unified home workflow records
   each successful observation at its actual local collection time, rather than
   assigning all observations the start time. Existing collector callers retain
   their original fixed-timestamp behavior unless they supply the new clock.
3. Save the monthly global snapshot after collection, retaining its real time.
4. Print current category/global valuation, historical snapshots and stage status.

Home only accepts today's local date in `--date`: it cannot backdate live Steam
observations. The actual clock controls observation and snapshot timestamps.
School uses `--date` as an exact valuation cutoff, including time of day. A bare
date means midnight, not the end of that day. Future snapshots are excluded from
the historical report. No data files are written in school mode.

## Result and failure behavior

- Exit **0**: complete current coverage, no collection failure and no held price
  older than 24 hours.
- Exit **1**: partial result, including a failed collection, missing category,
  unknown quantity, missing held price or held price older than 24 hours.
- Exit **2**: validation, I/O or processing failure. The stage summary identifies
  the failure and all successfully completed stages. Invalid CLI arguments also
  use argparse's exit status 2.

Known subtotals and complete totals remain distinct. A failed new price may reuse
a valid previous observation, whose age is displayed. Failed collection status
remains visible even when an older price permits a complete gross valuation.
Snapshots with incomplete data retain explicit coverage; they are not complete
portfolio totals. An entirely failed collection can still produce a partial
snapshot/report using saved prices.

Prices and global snapshots each use their existing atomic CSV replacement.
There is no transaction spanning both files: if snapshot writing fails after
prices are saved, the prices remain available. A subsequent invocation retries
the workflow. Identical item/source/timestamp observations replace each other;
later real timestamps are distinct observations, not duplicate retries. A new
snapshot replaces only its calendar month. Concurrent writers are not supported.
Collection resumption within a partially interrupted request batch, scheduling,
notifications and retry/backoff policies remain outside this issue.

## Validation

Synthetic tests cover the full sequence, real per-item timestamps, incomplete
collection with and without previous prices, validation before side effects,
snapshot-write failure and repeat-run recovery, configurable CLI paths, and
school-mode no-network/no-write behavior. No private CSVs or live Steam requests
are used by tests. The workflow reads existing processed data; it does not
regenerate spreadsheet exports or run notebooks automatically.
