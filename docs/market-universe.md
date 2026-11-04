# Independent market universe (#39)

The market universe, watchlist and owned portfolio are separate. Nothing here
changes an inventory quantity or its existing collection schedule.

Before importing or distributing catalog material, follow the
[ByMykel source/license review](third-party-sources.md) and preserve
[required notices](../THIRD_PARTY_NOTICES.md). Record the actual upstream revision
in each release; the license review reference is not a substitute for provenance.

Source selected for a first reviewed import: the unofficial
[ByMykel/CSGO-API](https://github.com/ByMykel/CSGO-API) English catalog.
Download a pinned Git commit's JSON locally and record its exact source URL,
commit in `source_revision`, source update and collection timestamps. This
release imports **reviewed exact Steam listings**, not a raw weapon-family name.
Source variant IDs must include wear/StatTrak/Souvenir distinctions. Float and
pattern premiums are outside coverage. No completeness claim is made, and no
third-party catalog has been downloaded or silently expanded in this PR.

Release JSON contract (synthetic selection):

```json
{"schema":1,"source_url":"https://github.com/ByMykel/CSGO-API",
 "source_revision":"replace-with-reviewed-commit","scope":"one reviewed case",
 "source_updated_at":"2026-11-01","collected_at":"2026-11-04",
 "items":[{"item_id":"use portfolio_data.identity(category, item_name)",
 "category":"case","item_name":"Example","market_hash_name":"Example Case",
 "source_id":"example-case","wear":null,"variant":"normal","collection":null}]}
```

```powershell
python src/market_universe.py home --publish data/market/reviewed.json
python src/market_universe.py school --release RELEASE_HASH --watchlist data/market/watchlist.json
python src/market_universe.py home --release RELEASE_HASH --watchlist data/market/watchlist.json --budget 20
```

Watchlist is a JSON array of stable item IDs. Every import is an immutable,
content-addressed release under ignored `data/market/releases`. Renames/category
changes create a new identity; `source_id` permits comparing successive releases.
Removed items remain in old releases and observations. Availability is measured
only for the selected watchlist, never the whole CS2 market. Missing prices are
unavailable, not zero. Report includes outcome, source metadata and age per item.

Collection uses one request per selected item, a two-second cadence and a hard
budget (default 20, maximum 1000), bounded timeout, classified failures and a
process lock. Resume by re-running an explicit selection: observations are
idempotent by item/source/run timestamp; older observations remain intact.
No unbounded retry or automatic market-wide collection. `school` performs no
network or write, including locks. Public endpoint volume/access may change.

`indices(root, release_id, watchlist, as_of)` freezes membership, retains its
release hash, uses equal item weights and excludes prices before catalog
availability or after the origin. It reuses shared freshness, zero-base and
coverage rules. No retrospective membership or portfolio weighting is inferred.
