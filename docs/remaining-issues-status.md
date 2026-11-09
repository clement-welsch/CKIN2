# Remaining-issue audit — 2026-11-09

This change targets `develop` directly. It combines the delivered #80/#82/#85
branches with the independently merged #87/#88 without losing either exact-object
reconciliation API. The original independent `/reconciliation` route is retained
in `dashboard_visible_route`; the integrated dashboard uses its scoped view.
Private CSVs, restored data and the user-confirmed AK quantity are outside this
change and are never used as test fixtures or committed.

| Issue | Result and evidence | Remaining limit |
|---|---|---|
| #38 | Existing local complete-owner/visible export parsing, exact reconciliation, token-bound apply, restore, idempotence, account scoping and failure tests audited | A real personal import still requires its explicit reviewed apply token; no private account was accessed |
| #39 | Existing versioned universe/watchlist/budget/index tests plus actual pinned 21,407-record source and three successful public price reads | Selection is 0.0140% of one file; no exhaustive market, liquidity or longitudinal forecast claim |
| #40 | Added real-corpus readiness checks and Research-page prerequisites; existing extraction, evidence and common-window experiments retained | Exact channels, authorized real corpus and dated manual review absent; empirical benefit unverified; remains open |
| #57 | Actual exact listing HTTP 200, candidate history HTTP 400 with decoded empty array; dated request hashes and negative access decision | Successful authorized capture and three graph comparisons absent; remains open, no backfill enabled |
| #79 | Seven notebooks audited as French reading reports with summaries, immutable presentation formatting and diagnostic appendices | No saved private outputs; model limits unchanged |
| #80 | Previously delivered compact current/historical summary integrated into this direct-develop change | Missing quantities/prices and unverified imports stay explicit |
| #82 | Previously delivered exact held-inventory table, deterministic sorting/filtering/paging and full-selection totals integrated | Catalog/watchlist records never become holdings |
| #83 | Explicit two-snapshot comparison with shared covered price/quantity effects, exclusions and calculable residual | Missing comparisons remain unavailable; quantity changes do not prove transactions |
| #84 | Compatible URL navigation, explicit presets/custom dates, active-filter removal and browser-only favorite lifecycle | Preferences do not sync; unavailable browser storage does not block consultation |
| #85 | Previously delivered data-quality centre and diagnosed partial reads integrated | Invalid dependent calculations stay blocked; no automatic repair or collection |
| #86 | Bounded primary-source image review and documented no-go, as allowed by the issue | No image/cache/download integration or blanket rights claim |

The technical portions of #40 and #57 are advanced as far as available evidence
allows. Their missing inputs are not replaced with fabricated transcripts,
channel identities, history, dates, graph measurements or positive study results.
