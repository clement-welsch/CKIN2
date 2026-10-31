# Global analysis (#26)

Open notebook/global_book.ipynb from the root or notebook directory. It reads
existing category exports, market_observations.csv and the global snapshot file.
No files are written. CKIN2_DATA_ROOT can select a separate synthetic data root
without changing the source checkout. Missing data produces diagnostics.

Current/historical portfolio values use actual quantities and backward prices.
Category totals reconcile to the global total when coverage is complete. Known
subtotals, unknown quantities, unimported categories and price ages are visible.
The comparison index is different: a fixed cohort of currently tracked objects,
equal weight per object, at a common exact observed base date. The global index
is equal weight over objects, not over category averages. It describes this
tracked portfolio, not a representative CS2 market index.

Acquisition references and estimated observation dates are excluded from indices.
The earliest common date is fixed for that cohort; a zero price at that date
makes comparison unavailable rather than silently moving the base. Later prices
are matched backward with a 45-day freshness limit. Index rows expose covered and
total item counts and the oldest price age. Any missing/stale cohort item makes
the corresponding index unavailable; weights never change to hide missingness.
Snapshot valuation can still use older prices, with age displayed separately.

Covered snapshot contributions use q0*(p1-p0) and (q1-q0)*p1, reconciling the
covered change exactly. Quantities absent from an imported category are zero;
unknown quantities and absent categories exclude the affected contributions.
The detail table and covered/total counts expose exclusions.

Validation executes every notebook cell on complete, partial and empty synthetic
datasets, serializes its four real Plotly figures on the complete fixture, checks
base-100 values and decomposition, and compares all CSV bytes before/after. This
checks figure construction and data, not pixel-level rendering in a browser.
Published notebook cells have no outputs or execution counts.
