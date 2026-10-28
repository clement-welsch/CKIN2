# Category notebook workflow

## Local setup

The validated environment is CPython 3.14.6. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m ipykernel install --user --name ckin2 --display-name "Python (CKIN2)"
```

Select **Python (CKIN2)** in the notebook editor. Installation in a fresh
environment has not yet been verified; the versions were read from the working
project environment. No Steam access is needed for local analysis.

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
