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
Manual price rows marked `source_column=0` survive regeneration. They identify
acquisition dates and reference values, never confirmed purchase costs.
Market rows sharing their date are retained separately.

Use these notebooks:

| Notebook | Scope |
| --- | --- |
| `notebook/cases_book.ipynb` | Drop cases, including existing inventory snapshots |
| `notebook/skins_book.ipynb` | Weapon skins and gloves |
| `notebook/souvenirs_book.ipynb` | Souvenir packages identified by tournament and map |
| `notebook/others_book.ipynb` | Stickers, charms and agents |

Acquisitions appear as separate markers and a timeline. Only market rows feed
indices, price coverage and inventory valuation. Estimated market dates appear
in hover details. Missing quantities keep complete totals unavailable. New
categories have no reconstructed historical quantity snapshots. Purchase costs
remain distinct from market reference values.

## Before committing

Clear all notebook outputs and execution counters using the editor, then save.
Saved tables and Plotly figures can reveal private holdings even while CSVs are
ignored. Inspect the staged diff, including notebook metadata. Do not add data
files with `git add -f`.

Run `python -B -m unittest discover -s test -q`. Tests use synthetic data and
do not require private CSVs or contact Steam. Local notebook execution is a
separate check and must not leave private outputs in the commit.
