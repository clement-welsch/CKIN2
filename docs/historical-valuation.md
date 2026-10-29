# Shared historical valuation

Tracking: #12. `notebook/cases_book.ipynb` replaces the former analysis notebook.

`calculate_historical_valuation(inventory_history, price_history)` returns two
DataFrames without changing its inputs:

- Detail: snapshot holdings plus the matched price `date`, `unit_price`,
  `market_value` and `priced_quantity`. Unpriced holdings have missing prices
  and price dates. Explicit empty-snapshot markers remain present.
- Summary: one row per snapshot, with known and complete values, held item-type
  coverage, total quantity and priced quantity. Empty input returns both schemas
  with no rows; an explicit empty snapshot returns a complete zero total.

Prices match backward on the exact snapshot timestamp, with no future price or
current-quantity reconstruction. Conflicting duplicate prices retain the existing
last-nonmissing-row rule. Both inputs use the existing validation contracts.

`calculate_historical_portfolio_value` remains the console-facing wrapper with
its original six summary columns. The notebook consumes the same detail and
summary instead of rebuilding joins and aggregations. Presentation percentages
and the two-snapshot price/quantity decomposition remain notebook concerns.

Validation: 39 synthetic tests passed on CPython 3.14.6, including direct
notebook/console comparisons for complete, partial and empty histories, absent
prices, zero observations, zero quantities, changing holdings and future prices.
Notebook calculation cells were executed against fixtures; personal notebooks
were not run against local CSVs.
