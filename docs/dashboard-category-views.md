# Category views (#52)

The local dashboard now has explicit navigation for overview, categories, item,
performance, forecasts, research and source attribution. Existing shared
calculations still produce portfolio values. Category pages do not execute
notebooks or train prediction models.

Open `http://127.0.0.1:8765/?page=categories`. Select one of six distinct
categories or show them all. Filters are retained when navigating; changing the
category clears the old item selection. The form retains the current view.

Each category shows value/coverage, held items, known-value contributions,
observation coverage, observed prices, per-item base 100 and separate acquisition
references. The normalization/index function is shared with category notebooks;
the existing chart function is reused. Indices use the first available market
price before the end cutoff, even when it precedes the display start. Zero bases
stay unavailable. Estimated dates are retained in chart hover details. Reference
values never become observed market prices or confirmed purchase costs.

The page uses the shared global loaders, including fresh collected prices and
reviewed Steam quantity overrides. Old category notebooks read their legacy
CSV inputs; parity is guaranteed for the same inputs, not for independently
updated datasets. No past quantities are inferred for newly imported categories.

Research is labeled as awaiting UI integration (#56); this PR does not imply
that research results or a detailed object page have been implemented. The
existing performance/forecast sections have their own views; their richer charts
remain tracked separately in #54/#55. Source attribution from #51 stays available.

Tests cover synthetic six-category reconciliation, notebook calculation parity,
reference separation, zero bases, unavailable data and read-only behavior.
