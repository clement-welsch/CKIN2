# Category notebook workflow

## Local setup

The supported reference environment is CPython 3.14.6, recorded in
`.python-version`. Install that interpreter first; `.python-version` does not
change the Python selected by PowerShell. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -B -m unittest discover -s test -v
.\.venv\Scripts\python.exe -m ipykernel install --user --name ckin2 --display-name "Python (CKIN2)"
```

Select **Python (CKIN2)** in the notebook editor. Direct dependency versions are
pinned in `requirements.txt`; transitive dependencies are resolved by pip, so
this is not a complete environment lock. Installation requires package-index
access. No Steam access is needed for local analysis.

For a fresh-install check without replacing an existing `.venv`, use
`.venv-ci` instead in the commands above and omit kernel registration. Both
environment directories are ignored by Git.

On 2026-10-28, a fresh Windows `.venv-ci` using CPython 3.14.6 installed
successfully from `requirements.txt`. `pip check` reported no conflicts, all
notebook dependency imports succeeded, and all 36 synthetic tests passed.
Linux installation remains subject to the first successful CI run.

## Continuous integration

`.github/workflows/tests.yml` installs dependencies on clean Windows and Linux
runners with the Python version from `.python-version`. It runs `pip check`,
checks imports for notebook dependencies, and executes the synthetic unittest
suite on pushes and pull requests. It can also be started manually from Actions.
The workflow uses no Steam credentials or private CSVs and does not execute the
personal-data notebooks. A successful local test run does not establish that
the remote workflow has passed; check both jobs on GitHub after publication.

## Data and analysis

Run `python src/process_categories.py` with the project environment active.
The converter reads the four local exports in `data/raw/`. Category inventories
and prices are written to `data/processed/`, excluded from Git.

Existing drop-case files are preserved. Category inventory files and ordinary
market rows are regenerated; edit raw exports for persistent corrections.
Manual price rows marked `source_column=0` survive regeneration, including numeric
zero representations such as `0.0` and `0.00`. Their original fields are retained;
invalid, missing or fractional source-column markers stop conversion before any
exports are rewritten. They identify
acquisition dates and reference values, never confirmed purchase costs.
Market rows sharing their date are retained separately.

Use these notebooks:

| Notebook | Scope |
| --- | --- |
| `notebook/cases_book.ipynb` | Drop cases, including recorded global snapshots |
| `notebook/skins_book.ipynb` | Weapon skins and gloves |
| `notebook/souvenirs_book.ipynb` | Souvenir packages identified by tournament and map |
| `notebook/others_book.ipynb` | Stickers, charms and agents |

Acquisitions appear as separate markers and a timeline. Only market rows feed
indices, price coverage and inventory valuation. Estimated market dates appear
in hover details. Missing quantities keep complete totals unavailable. Historical quantities come
only from recorded global snapshots; no category history is reconstructed from
current holdings. Purchase costs remain distinct from market reference values.

## Shared portfolio contract (#78)

All four category notebooks use `notebook_data.category_report`: the same
`load_holdings`, `load_prices`, snapshot valuation, selection and category price
normalization as the dashboard. Recent `market_observations.csv` rows are included;
`source_column=0` references are displayed separately. Exact identities preserve
wear, StatTrak and Souvenir variants; a catalog/watchlist entry creates no quantity.
The cases fixed-basket index now uses the held cohort and shared freshness rules,
rather than every identity ever seen in its price file.

`CKIN2_DATA_ROOT` selects the data root independently of the code checkout.
`CKIN2_AS_OF` fixes a timezone-naive analysis timestamp, for example in PowerShell:

```powershell
$env:CKIN2_DATA_ROOT = "C:\local\CKIN2"
$env:CKIN2_AS_OF = "2026-11-09 12:00:00"
```

The date defaults to now. In category notebooks `HISTORICAL=False` means **current
known quantities**, priced only with observations available at that date. It is
not a claim that today's quantities existed at a past date. Set `HISTORICAL=True`
to select the last recorded global snapshot at or before `AS_OF`, matching the
dashboard's historical end-date behavior. Dashboard end dates include the entire
day, so compare with `AS_OF="YYYY-MM-DD 23:59:59.999999999"`. No prior snapshot
means an unavailable historical total, not today's inventory. Each historical
curve independently keeps its own snapshot quantities. The legacy case-only
history CSV is not silently combined with the six-category snapshot contract;
use the global snapshot workflow for these reports.

An explicitly full-portfolio owner override supplies the current holdings.
Cached public visible observations never change those quantities. Notebook and
dashboard report owner-declared, unverified legacy-override or manual-CSV
provenance. CSV capture dates remain unknown; file modification time is not used
as evidence. Declared CSV purchase references remain available for CSV holdings,
but are not carried into owner replacements or historical lots without evidence.
FIFO remains the separate source for documented lot costs and gains/losses.

Global, prediction and research notebooks also print their data root, analysis
date and scope. Global uses the shared portfolio analyzer; prediction keeps its
current fixed cohort and existing archive-aware price loader, while research
uses the independent market universe, not portfolio quantities. Prediction
models and forecast/archive contracts are unchanged. Reading notebooks never
collects prices or writes inventories. Synthetic tests execute every category
notebook on complete, partial and empty fixtures, plus the owner replacement case.

## Before committing

Repeated market observations for the same item and timestamp use the last
nonmissing price in file order, retaining its metadata. This selection is shared
by category charts, base-100 indices, observation counts and valuation.

Clear all notebook outputs and execution counters using the editor, then save.
Saved tables and Plotly figures can reveal private holdings even while CSVs are
ignored. Inspect the staged diff, including notebook metadata. Do not add data
files with `git add -f`.

Run `python -B -m unittest discover -s test -q`. Tests use synthetic data and
do not require private CSVs or contact Steam. Local notebook execution is a
separate check and must not leave private outputs in the commit.
