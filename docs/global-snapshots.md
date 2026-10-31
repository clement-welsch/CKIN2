# Global monthly snapshots (#24)

```powershell
python src/global_snapshots.py home
python src/global_snapshots.py school
```

Home records existing quantities; it does not implicitly collect prices. Run the
multi-category collector first if fresh prices are wanted. School only reads.
One atomic CSV, data/processed/global_inventory_history.csv, contains every
category at each snapshot date. Re-running in the same calendar month replaces
the entire snapshot, preserving other years and months. Validation completes
before replacement. Concurrent writers are not supported.

States are holdings, empty and not_imported. A missing inventory file is not an
empty inventory. An imported others file covers stickers, charms and agents,
including empty subcategories. Missing quantities remain unknown. Explicit empty
markers have no item identity and quantity zero. No category may be omitted from
a global snapshot. A truly empty, completely imported portfolio has value zero.

Valuation uses each snapshot's quantities and only prices at or before that
snapshot. Summaries expose known subtotal, complete total, item-type price
coverage, unknown quantities, absent categories and oldest price age in days.
Incomplete totals remain unavailable. Gross EUR prices are used; acquisition
references are excluded. Historic changes include changes in quantities.

Existing case snapshots and all category exports remain untouched. Global history
begins when this command is first run; earlier global holdings are not invented.
Legacy market observations without a time of day are interpreted at midnight on
their recorded date. New snapshots are dated at midnight, so prices collected
later the same day are intentionally unavailable to that midnight snapshot.
Run a snapshot on the following day to include those observations. This preserves
the strict no-future-price rule.

Tests verify complete-category reconciliation, unknown/empty/absent states,
future-price exclusion, empty transitions, year/month retention, repeat-run
idempotence, failed atomic replacement, corrupt-history preservation and read-only
school reports. No network or private data is used.
