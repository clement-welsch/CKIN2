# Reading the notebooks as reports (#79)

All seven notebooks now start with their scope, analysis date/root and the
available result or a concrete unavailability explanation. Their authored code
remains accessible; standard Jupyter source-hidden metadata makes a rendered
report easier to read. Long inventories, coverage tables, chronological windows,
source records and audits are in named diagnostic appendices rather than leading
the main reading path. Appendix code/output can be expanded for inspection.

| Notebook | Main question | Distinction retained |
|---|---|---|
| cases | What are the known case value and observed price movements? | Current holdings versus recorded global snapshots; base-zero indices unavailable |
| skins | What are the skin positions worth with available prices? | Acquisition reference versus market price and documented purchase cost |
| souvenirs | What is covered in the souvenir portfolio? | Exact item names and recorded quantities, no inferred history |
| others | How do stickers, agents and charms contribute? | Separate categories and incomplete quantities/prices |
| global | What is the portfolio value, distribution and covered change? | Value versus fixed-cohort price index versus quantity effect |
| prediction | Which next-month index forecasts and common-window errors exist? | Experimental index points, not EUR value, profits or issued forecasts |
| community | Is the local corpus adequate and is comparison measurable? | Creator claims, verified facts, extraction review and forecasting evidence |

`notebook_reporting` formats copies for presentation: French labels, readable
dates, integral quantities/counts, comma decimals, EUR and percent units, and
explicit unavailable values. Plot wrappers copy categorical display labels
without mutating analytical frames. Current/historical valuation, normalization,
FIFO, prediction models, sample windows and the archive contract are unchanged.
No notebook collects data, writes portfolio files or saves private outputs.

Existing full execution tests cover complete/partial/empty fixtures and owner
replacement, including exact parity with shared calculations, unknown quantities,
base-zero behavior and future-data exclusion. Research notebooks also execute
with an absent or populated synthetic corpus. Figures are serialized in tests;
notebooks are committed with empty outputs/execution counts.
