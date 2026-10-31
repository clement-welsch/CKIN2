# Understanding portfolio snapshots

For the unified command, its `--date` / `--snapshot-path` options,
exit statuses and recovery behavior, see [the workflow guide](one-command-update.md).
Home uses real collection timestamps and cannot backdate live prices.

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
