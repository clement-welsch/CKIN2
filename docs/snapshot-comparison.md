# Comparing recorded snapshots (#83)

The Comparison view selects two exact recorded timestamps, in chronological
order, within the analysis cutoff and optional start date. Category and exact
item filters apply before valuation and decomposition. The two dates, category
states, known/full values and missing quantities/prices remain visible.

The shared `value_snapshots` and `explain_changes` functions supply the numbers:
`q0 * (p1 - p0)` is the price effect; `(q1 - q0) * p1` is the quantity effect.
Their sum equals `q1*p1 - q0*p0` on comparable rows. Each endpoint uses its own
recorded quantities and backward-as-of prices. No current quantity is projected
into either endpoint and no future observation is used.

The contributor list retains excluded identities and links to exact object
pages. Covered effects are plotted separately by category. A complete value
change and residual are calculated only when both full values and the covered
change exist. Missing values stay unavailable; a known subtotal is not silently
substituted for a full value. Identical complete snapshots legitimately yield
zero; missing/unknown data does not become zero. A recorded empty portfolio is
distinct from no snapshot or an unimported category.

A change in quantity is not labeled an acquisition, sale or transfer without
transaction evidence. Value changes are not investment returns or FIFO profits.
The view is read-only and never saves snapshots. Synthetic tests verify covered
reconciliation, identical/absent/incomplete snapshots, zero prices, missing
quantities, reversed/unknown dates, filters and byte-preserving rendering.
