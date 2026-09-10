# CKIN2

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
├── notebooks/
│   ├── 01_import_data.ipynb
│   ├── 02_data_cleaning.ipynb
│   ├── 03_price_analysis.ipynb
│   └── 04_visualization.ipynb
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

* [ ] Calculate current inventory value
* [ ] Calculate profit / loss
* [ ] Analyze portfolio performance
* [ ] Analyze individual skins

### V3 — Visualization

* [ ] Portfolio value chart
* [ ] Price evolution charts
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
