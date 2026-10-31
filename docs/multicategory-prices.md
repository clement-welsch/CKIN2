# Multi-category prices (#23)

Run from the repository root after the existing CSV conversion:

```powershell
python src/update_market_prices.py home --init-catalog
# Review data/processed/market_catalog.csv before the first collection.
python src/update_market_prices.py home
python src/update_market_prices.py school
```

The catalog is private, ignored data. Non-case listing names are deliberately
blank in a new template: enter each exact Steam market_hash_name including wear,
StatTrak/Souvenir and other listing variants. Case names preserve the existing
Case/Terminal convention. The collector rejects blank, stale, duplicate or
ambiguous mappings before contacting Steam. When the inventory changes, edit
the catalog to match its current identities; initialization never overwrites it.

Identity is UUID5 of the exact category and item name. Renaming an object changes
its identity; there is no fuzzy matching. The new file market_observations.csv
stores source=steam, currency=EUR, local timestamp (seconds) and
date_estimated=False. A retry at an identical item/source/timestamp replaces that
observation; a later timestamp is a new observation. Collection is sequential
with a two-second interval and the existing bounded request timeout. HTTP 429
and other failures do not append fake observations. No backfill or scheduled job
is installed. Console output reports item-level freshness and category coverage.

Legacy CSVs are read-only inputs and remain compatible. Acquisition references
(numeric source_column=0) are excluded from market prices. New observations are
kept separately so re-running spreadsheet conversion cannot erase them. School
mode neither contacts Steam nor writes files. The original case collector and
its command retain their behavior. Prices remain gross EUR listing estimates.

Validation: synthetic multi-category fixtures, exact URL requests through the
existing Steam decoder tests, repeat-run persistence, failure retention,
school-mode no-network/no-write behavior and acquisition exclusion. Live Steam
availability and manually supplied listing mappings are not verified by tests.
