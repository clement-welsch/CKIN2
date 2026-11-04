# Assisted Steam inventory import (#38)

The first adapter accepts a **local JSON export**, including private inventories
exported by their owner. It does not log into Steam or collect credentials.
Steam asset identity is retained in an ignored audit; the exact market name is
matched against your reviewed `market_catalog.csv`. Ambiguities/unknown objects
block application. Map variants to distinct catalog entries before retrying.

Envelope schema: `schema: 1`, `account_id` (string, one account), `collected_at`
(local naive ISO timestamp), `complete: true`, `pages: [...]`. Each page contains
Steam's `success: 1`, `assets`, `descriptions`, and integer `more_items: 0|1`.
For multiple pages record `last_assetid` and the next page's `start_assetid`.
The first page has no `start_assetid`. Last page must explicitly have
`more_items: 0`; an empty inventory still requires empty assets/descriptions.
Assets require string `assetid`, `classid`, `instanceid`, `amount`, appid 730,
contextid 2. Descriptions require appid/classid/instanceid/market_hash_name.
No remote completeness guarantee is inferred from an arbitrary file: export it
in one consistent session and review the preview. Identical repeated assets are
counted once; contradictory duplicates, missing descriptions and broken page
chains fail. No purchase price, acquisition date or transaction is inferred.

```powershell
python src/steam_inventory.py school --export data/imports/export.json --catalog data/processed/market_catalog.csv
python src/steam_inventory.py home --export data/imports/export.json --catalog data/processed/market_catalog.csv --apply-token REVIEW_TOKEN
python src/steam_inventory.py home --restore
```

Preview reports old/new quantities, deltas, unresolved listings and the review
token. Application recomputes that plan against current files; stale tokens
fail. Repeat application of the same source is a no-op. Different accounts and
older exports are rejected. Multi-account aggregation is deliberately explicit:
do not replace one account with an export of another.

Application atomically publishes **one authoritative quantity override** under
`data/processed/steam_inventory_override.json`, read by shared `load_holdings`.
The four legacy inventory CSVs and all costs remain untouched. An immutable
content-addressed backup under `data/imports` preserves the previous override,
prior effective holdings and asset-level import trace before publication.
`--restore` reverts the last override. Snapshot/report workflows consume the
override; the old category-only notebooks still read their original CSVs.
Edit/reimport the Steam source to update overridden quantities; editing legacy
CSV quantities has no effect while the override is active. `school` never
writes. A complete import covers all six supported categories; unsupported Steam
objects must be resolved deliberately rather than silently discarded.
