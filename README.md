# CKIN2

Development history, dated feature summaries, validation notes and pull request
links are recorded in the [development journal](docs/journal.md).

For a single command that validates data, updates market prices, saves a global
snapshot and prints the portfolio report, see the
[one-command update workflow](docs/one-command-update.md).

**CKIN2** is a personal project designed to track and analyze my **Counter-Strike 2 skin inventory**.

The goal is to centralize my inventory data, maintain a historical record of its value, and progressively develop analysis tools to better understand the evolution of my skin portfolio.

---

## 🎯 Objectives

The project has several objectives:

1. **Store my inventory**

   * Skin name
   * Condition (*Factory New, Minimal Wear, etc.*)
   * Quantity
   * Purchase date
   * Purchase price

2. **Track prices**

   * Retrieve skin prices at a given point in time
   * Store historical price data
   * Compare current prices with previous observations

3. **Analyze portfolio performance**

   * Total inventory value
   * Value evolution over time
   * Profit / loss
   * Individual skin performance

4. **Visualize the data**

   * Portfolio value over time
   * Individual skin price evolution
   * Skin comparisons
   * Inventory value distribution

5. **Develop decision-support tools**

   * Identify skins worth monitoring
   * Detect significant price movements
   * Provide indicators that can support buy, sell, or hold decisions

> Decision-support indicators are intended for analytical purposes and should not be considered financial advice.

---

## 🚧 Project Status

The project is currently in the **data structuring and migration phase**.

### Initial step

My historical data is currently stored in a **Google Sheet**, which I update approximately once a month.

The first version of CKIN2 focuses on:

```text
Google Sheets
      ↓
Export individual sheets
      ↓
CSV files
      ↓
Load data with Pandas
      ↓
Data cleaning / normalization
      ↓
Structured datasets
      ↓
Analysis
```

The initial goal is to retrieve:

* owned skins;
* skin condition;
* quantity;
* purchase date;
* purchase price;
* historical price evolution up to the present day.

---

## 🗂️ Project Structure

The project structure is expected to evolve as development progresses.

```text
CKIN2/
│
├── data/
│   ├── raw/
│   │   └── CSV data exported from Google Sheets
│   │
│   └── processed/
│       └── Cleaned and prepared datasets
│
├── notebook/
│   ├── cases_book.ipynb
│   ├── skins_book.ipynb
│   ├── souvenirs_book.ipynb
│   └── others_book.ipynb
│
├── src/
│   ├── data/
│   ├── analysis/
│   └── visualization/
│
├── test/
│
├── .gitignore
├── README.md
└── requirements.txt
```

The exact structure may be adapted as the project requirements become clearer.

---

## 🐍 Technologies

The project primarily uses the Python ecosystem for data manipulation and analysis.

### Language

* **Python**

### Data Analysis

* **Pandas** — data manipulation and analysis
* **NumPy** — numerical computing

### Data Visualization

* **Matplotlib**
* **Seaborn**

### Analysis Environment

* **Jupyter Notebook**

Additional libraries may be introduced as the project evolves.

---

## 📊 Data

The historical data initially comes from a personal Google Sheet.

The main information currently being processed includes:

### Inventory

```text
Skin
Condition
Quantity
Purchase date
Purchase price
```

### Price History

```text
Skin
Condition
Observation date
Price
```

Keeping inventory data and price history separate makes it possible to distinguish between:

* **what I own**;
* **the market value observed at a given point in time**.

This distinction will be important for future analysis.

---

## 📈 Planned Analysis

Once the data has been properly structured, CKIN2 will provide various portfolio and market indicators.

### Portfolio

* Current total value
* Historical portfolio value
* Portfolio value evolution
* Value distribution by skin
* Distribution by skin type / rarity / collection

### Performance

* Purchase price
* Current price
* Profit / loss
* Return on investment
* Cumulative performance

### Price Evolution

* Daily or monthly price changes
* Trends
* Volatility
* Drawdown
* Skin-to-skin comparisons

---

## 🔮 Future Development

The project will progressively evolve into a complete skin portfolio tracking and analysis tool.

### V1 — Data Import & Structuring

* [x] Existing historical data
* [ ] Google Sheets → CSV export
* [ ] Load CSV files with Pandas
* [ ] Data cleaning
* [ ] Date and price normalization
* [ ] Build consistent datasets

### V2 — Analysis

* [x] Calculate current inventory value
* [ ] Calculate profit / loss
* [x] Analyze portfolio performance
* [ ] Analyze individual skins

Run the portfolio report from the project root once a month, after updating
`data/processed/drop_cases_inventory.csv` with current quantities. In `home`
mode, it retrieves prices, calculates the current inventory value, and saves
that month's inventory snapshot to
`data/processed/drop_cases_inventory_history.csv`. Running it again in the same
month replaces that month's snapshot. Historical values use the latest recorded
price on or before each snapshot date. In `school` mode, it values the inventory
with the latest saved prices. Since those prices were not freshly retrieved
from Steam, school mode is fully read-only: it does not write price history or
inventory snapshots.

```powershell
python src/portfolio_report.py home
python src/portfolio_report.py school
```

Reports distinguish `known_value` (the subtotal of priced holdings) from
`total_value` (available only when every held item has a price). Price coverage
counts held item types, not units. Zero-quantity rows do not require a price;
an empty inventory has a complete value of zero. When no held item can be
priced, both values are unavailable rather than zero.

The same rules apply to monthly snapshots. Historical totals remain unavailable
on incomplete dates, and the notebook does not calculate changes across those
gaps. Notebook weights are percentages of known value, excluding unpriced
holdings. Changes between snapshot totals also reflect quantity changes and
must not be interpreted as investment returns.

Input validation raises `ValueError` for missing required columns, blank or
non-string item identifiers, identifiers with surrounding whitespace, invalid
dates, and invalid numeric values. Quantities must be present, finite,
nonnegative whole numbers. Prices must be finite and nonnegative when present;
missing prices remain unavailable, while an observed zero price is retained.
Boolean values are rejected as numbers. Numeric strings are accepted.

Dates must be present and timezone-naive; timestamps retain their time of day
for price matching. Item names are matched exactly, including case. Duplicate
inventory holdings are rejected (per item for the current inventory, per item
and snapshot timestamp for history). Repeated price observations retain the
last nonmissing price in file order for each item and timestamp, with a warning
if those prices conflict. Input DataFrames and source CSV files are not cleaned
or rewritten by the calculation functions. Snapshot saving validates both the
incoming inventory and existing history before writing.

Use CPython 3.14.6, recorded in `.python-version`, and install the pinned direct
dependencies before running the automated tests from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -B -m unittest discover -s test -v
```

Tests use synthetic inputs and temporary files under `test/`; they do not
contact Steam or write to `data/`. Coverage includes partial valuations, invalid
inputs, school-mode read-only behavior, monthly snapshot replacement, retention
of other months and years, repeat-run idempotence, and valuation using each
snapshot's own holdings. Selected notebook calculation cells are checked with
synthetic data; this does not replace a full notebook run with local CSV files.

GitHub Actions runs this suite on clean Windows and Linux runners for pushes
and pull requests. See [setup and CI details](docs/category-notebooks.md).
Direct dependency versions are pinned; transitive dependencies are resolved
by pip rather than fully locked.

### V3 — Visualization

* [x] Portfolio value chart
* [x] Price evolution charts
* [ ] Skin comparison charts
* [ ] Dashboard

### V4 — Automated Data Collection

* [ ] Automatically retrieve skin prices
* [ ] Store price observations
* [ ] Automatically update historical data

### V5 — Decision Support

* [ ] Detect significant price movements
* [ ] Trend indicators
* [ ] Volatility / risk analysis
* [ ] Buy / sell / hold decision-support tools
* [ ] Use scikit-learn to forecast price or portfolio-value changes between monthly CKIN2 updates once enough history has been collected

---

## ⚠️ Limitations

CS2 skin prices can be highly volatile and may depend on several factors, including:

* marketplace;
* supply and demand;
* liquidity;
* skin condition;
* float value;
* pattern;
* observation period.

The analyses produced by CKIN2 should therefore be considered **data analysis tools**, rather than guarantees or predictions of future prices.

---

## 🔐 Data Privacy

The inventory data used by CKIN2 is personal.

Files containing private or sensitive information should not be committed to Git.

The `.gitignore` file should be used to exclude personal data and local configuration files from version control.

---

## 📌 Project Philosophy

CKIN2 is primarily a personal learning and experimentation project focused on:

* data collection;
* data cleaning and transformation;
* statistical analysis;
* data visualization;
* automation;
* and, eventually, the application of data science and machine learning techniques to a real-world market.

The project follows a **progressive, data-driven approach**, starting by making the historical data reliable and structured before introducing more advanced analytical or predictive methods.


## Category notebooks and local CSV conversion

Run `python src/process_categories.py` from the project root to normalize the
four exports in `data/raw/`. This regenerates `skins_inventory.csv`,
`skins_prices.csv`, `souvenirs_inventory.csv`, `souvenirs_prices.csv`,
`others_inventory.csv`, `others_prices.csv`, and `category_import_issues.csv`
in the ignored `data/processed/` directory. Existing drop-case inventory and
price files are preserved; they are imported from raw only when absent.
Re-running the converter regenerates ordinary market observations from raw.
Manual acquisition references marked `source_column=0` in the three category
price CSVs are preserved, including items no longer present in raw and references
sharing a date with a market observation. Repeated runs do not multiply these
references. Other manual edits to generated rows are replaced; edit raw instead.
Acquisition references represent acquisition dates and reference values, not
confirmed purchase costs. They never populate `purchase_unit_price` or
`purchase_date`. Existing price schemas are checked before any exports are written. The converter never contacts Steam.

Open `notebook/cases_book.ipynb`, `notebook/skins_book.ipynb`,
`notebook/souvenirs_book.ipynb`, or `notebook/others_book.ipynb` using the project
Python environment with pandas, NumPy, Plotly, and IPython installed. These
notebooks only read CSVs. Agents and charms in the skins source are grouped with
stickers in the others category. Souvenir identifiers include tournament and map.

Category inventory columns are `item_name`, `item_type`, `quantity`,
`purchase_unit_price`, and `purchase_date`. Market history uses `date`,
`item_name`, `unit_price`, `date_estimated`, `source_file`, and `source_column`
(one-based column numbers). Source totals and tournament headings are excluded;
decimal commas are converted and missing values stay missing.

The first numerical skins column after quantity is the unit purchase price,
with unknown purchase date. Undated market columns bounded by dated columns
are interpolated between those dates and marked `date_estimated=True`; fractional
days are truncated to the calendar day. No purchase date is inferred from market
prices. Missing quantities are reported and excluded from the known subtotal;
the complete portfolio total remains unavailable. New categories do not invent
historical inventory snapshots or apply current quantities to historical prices.

Category notebooks exclude source_column=0 acquisition references from market
indices, price coverage, and valuation. Reference values appear as separate
crosses on the price chart; acquisition dates also have their own timeline.
Estimated market dates are identified in hover details. An acquisition-only item
has no market valuation until a market observation is available.

See [the category workflow](docs/category-notebooks.md) for setup, data contracts
and notebook privacy checks, and [the development journal](docs/journal.md) for
this branch. Install the validated dependencies with
`python -m pip install -r requirements.txt` (validated Python: 3.14.6).
