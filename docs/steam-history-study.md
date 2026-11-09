# Steam history feasibility study (#57)

## Current decision: pending live validation

Development was performed at M2I in `school` mode. No Steam page, internal
endpoint, authentication or terms were accessed or tested. **There is no live
go/no-go result.** #57 remains open and #58 must not start importing/backfilling
real history until the access study is positive. Existing price observations,
quantity snapshots and collectors are unchanged.

The included JSON is entirely synthetic. Its price triples, English month names,
hour/offset syntax, volume grouping and EUR/currency=3 mapping are an explicit
working hypothesis to compare with a real capture, not a supported Steam API
contract. Even successful offline parsing proves neither access nor reuse rights.

## Offline preparation

```powershell
.\.venv-ci\Scripts\python.exe src/steam_history_study.py school --capture config/steam-history-study.synthetic.json
```

The command reads one sanitized local JSON envelope and prints a diagnostic to
stdout. It has no network client and writes no files. It validates exact listing
and response identities (appid 730, exact market hash name), explicit retrieval
timezone, finite nonnegative prices, integer volume and unique observation times.
Dates normalize to UTC independently of Windows locale. Zero prices/volume remain
valid; empty data remain unavailable, never evidence of no sales. Missing periods
are preserved. Observed spacings do not establish the source's aggregation
granularity. Unknown formats fail for review rather than being guessed.

The analyzer deliberately accepts only declared EUR in this initial study.
Additional currencies need a checked mapping and separate units. The price
measure remains unverified until the following manual checks are complete;
never append these triples to `market_observations.csv`, where listing minimums
and legacy observations have a different meaning.

## Manual validation on an authorized home network

1. Select one real, reviewed `market_hash_name` from the local market catalog.
   Open its exact listing manually. Record item identity, wear, StatTrak/Souvenir
   variants and final URL. Reject redirects/grouped pages that change identity.
2. Review the current Steam access/reuse conditions and applicable source
   documentation on that network. Record URLs, review date and actual restrictions.
   Do not assume an internal graph endpoint is a guaranteed public API.
3. Inspect that one listing's graph request in browser developer tools. Record
   endpoint, status, response content type, request currency, retrieval time with
   offset and whether the browser was signed in. Determine whether the graph/page
   exposes the series or uses `pricehistory`; do not assume the candidate path.
4. If permitted, compare the same single request with and without a normal local
   session to establish actual authentication requirements. Stop on denied access,
   login HTML, rate limits or an unexpected redirect. No bypass, retries or batch
   collection. Never export a HAR, cookies, headers or credentials into Git or chat.
5. Save only the sanitized response body and the envelope metadata under ignored
   `data/steam_history_study/`. Keep session handling in the browser. Confirm
   the capture contains no account/session data before using the offline analyzer.
   Adapt the parser only to a reviewed observed schema; an unsupported body is not
   a reason to coerce prices, currencies or timestamps.
6. Compare at least three dated points against the graph at different zoom/ranges.
   Record displayed time/timezone, currency, price and volume. Establish whether
   prices are sales medians, another sale statistic, or listing minimums; compare
   listing minimum separately. Record earliest/latest available points, spacing,
   aggregation changes and holes. Do not infer an exact price at an arbitrary time.
7. Write a dated decision using the template below. A positive result requires
   actual access, exact identity/currency, graph parity, understood time/measure,
   and an acceptable documented acquisition/reuse method. Otherwise record no-go
   or pending with the missing evidence. Do not mark #57 complete from synthetic
   tests. #58's cache/import design follows this decision.

## Evidence / decision template (local, no secrets)

| Check | Observed evidence |
|---|---|
| Date, authorized network, reviewer | pending |
| Exact name, variant, listing and final URL | pending |
| Endpoint / page extraction, HTTP result, content type | pending |
| Authentication actually required | pending |
| Currency and price definition | pending |
| Raw timezone, normalized UTC, displayed graph timezone | pending |
| Earliest/latest points, count, observed spacing and holes | pending |
| Three graph comparisons: date, price, volume, difference | pending |
| Access/reuse sources, review date and restrictions | pending |
| Sanitized local sample path, parser compatibility | pending |
| Decision: go / no-go / pending, reasons and limits | pending |

Historical prices never reconstruct quantities owned. Backfilled history also
needs availability/provenance rules before forecasting experiments may use it;
retrieving past observations today does not prove they were available to a model
at every historical origin. No forecasting integration is included in this study.
