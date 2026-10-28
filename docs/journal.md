# Development journal

## 2026-10-28 - Category notebooks

Branch: `Klement/feat/category-notebooks`.

- Replaced the single notebook entry point with dedicated cases, skins,
  souvenirs and others notebooks.
- Added reproducible conversion of raw spreadsheet exports into category
  inventories and market histories, preserving existing case files.
- Preserved manual acquisition reference rows across repeated conversions.
- Separated acquisition references from market indices and valuation; added
  acquisition markers, timelines and estimated-date hover details.
- Added regression tests and documented missing-data and purchase-cost limits.
- Declared the dependency versions used in the working Python 3.14.6 environment.
- Cleared saved notebook results before publication to protect local data.

Validation: 36 tests passed during the latest functional verification; all four
notebooks executed successfully and generated 16 figures without changing CSVs.
Fresh-environment installation and automated CI remain follow-up work in #11.

Local inventory corrections stay outside Git. No private quantities, acquisition
dates or prices are recorded in this journal.

Tracking: [#16](https://github.com/clement-welsch/CKIN2/issues/16) covers
category conversion and notebooks. [#11](https://github.com/clement-welsch/CKIN2/issues/11)
remains open for dependencies, fresh-environment installation and CI.
