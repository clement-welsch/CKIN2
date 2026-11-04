# Exact item detail (#53)

Open the **Fiche objet** view and search a literal name fragment or select an
exact identity. Category, period and variant remain explicit. Search matches
case-insensitively without fuzzy merging; variants retain distinct IDs.

The registry includes current holdings, historical holdings, known market
observations, the reviewed local catalog and eligible immutable market releases.
Future-dated releases/prices are excluded. Imported metadata is displayed as
declared, with source/revision; no wear/variant is guessed from a name. Objects
need not be owned. A followed object without a position is explicitly labeled;
the catalog never supplies a personal quantity.

The page reuses notebook market normalization/base-100 charts, acquisition
reference markers, and global snapshot valuation. Independent watchlist prices
from `data/market/observations.csv` supplement processed market observations
on this page. Personal summary/category views continue to use their existing
processed inputs; the selected item's detail displays its own source dates.
Same-item/timestamp duplicates follow the shared last-nonmissing rule; the
independent observations are appended last, and conflicting prices warn.

The price chart shows actual recorded observations, not an imported Steam median
sale history (that adapter is still planned). Missing observations remain gaps;
estimated dates are marked. Base 100 uses the first nonmissing market price
before the end cutoff, even outside the visible start; a zero base is unavailable.
References appear as separate markers and never become market prices.

Selected holdings are valued with the shared quantity/coverage contract. Past
views retain their recorded snapshot timestamp and match prices on or before
that timestamp. The chart can extend to the requested end after that snapshot;
its newest price is not silently used to reprice the older snapshot.

Explicit purchase CSV fields are displayed as declared. Unknown cost/date stays
unknown; acquisition references do not imply a purchase. A declared unit price
does not establish current lot cost or latent profit. Gains/remaining basis are
shown only when the existing FIFO module can produce them, including its
unavailable/mismatch diagnostics. No sales fees or ROI are invented.

The page links **Sources et licences**, retaining ByMykel attribution and the
scope of the pinned license review. All loading is local/read-only. Full-history
and synthetic tests cover owned/unowned items, variants, future exclusions,
purchase unknowns, reference separation, missing-price gaps and zero bases.
