# Projeto_Etd

A modular ETL pipeline developed for the **Data Extraction and Transformation (ETD)** course. The project collects, integrates, transforms, and stores macroeconomic indicators from the **World Bank** and complementary sources, consolidating them into an analytical **Data Warehouse** designed for exploration and data analysis.

---

## Objective

The main objective of this project is to implement a complete ETL architecture capable of:

- Extracting data from multiple sources.
- Ensuring data quality and consistency.
- Integrating different economic datasets.
- Building a dimensional model for historical analysis.
- Providing structured data for analytical workloads.

---

## Selected Domain

The selected domain is **Global Economy and Development**.

The analysis focuses on macroeconomic and social indicators published by the World Bank, enabling the study of economic trends across countries over time and the identification of patterns between regions and income groups.

Analyzed indicators include:

- Gross Domestic Product (GDP)
- Inflation
- Unemployment
- Economic Growth
- Complementary Social Indicators

---

## Project Architecture

```text
Projeto_Etd/
├── data/
│   ├── gold/
│   │   └── wdi_gold.csv
│   │
│   ├── db/
│   │   └── analytics_dw.db
│   │
│   ├── logs/
│   │   ├── load.log
│   │   └── transform.log
│   │
│   ├── silver/
│   │   └── wdi_staging.csv
│   │
│   └── raw/
│       ├── bulk/
│       │   ├── WDICSV.csv
│       │   └── WDICountry.csv
│       │
|       └── api/
│           └── gdp_add.json
|       |
│       └── extra/
│           └── gdp.csv
│
├── docs/
├── sql/
│   └── schema.sql
│
└── src/
    ├── __init__.py
    ├── config.py
    ├── extract.py
    ├── transform.py
    └── load.py
```

---

## Technologies Used

- Python 3
- Pandas
- Requests
- SQLAlchemy
- SQLite
- World Bank API

---

## Data Sources

### 1. World Bank (World Development Indicators)

Primary data source used throughout the project.

### 2. World Bank API

Used to retrieve up-to-date information directly from World Bank services.

### 3. Complementary Source

Additional dataset (`gdp.csv`) used to enrich and validate the primary source.

---

## Environment Setup

### 1. Obtain Bulk Data

Due to file size limitations, raw datasets are not included in the repository.

1. Access the official World Bank Data Catalog.
2. Download the **CSV File** package from the **World Development Indicators (WDI)** dataset.
3. Extract the files into:

```text
data/raw/bulk/
```

Expected files:

```text
WDICSV.csv
WDICountry.csv
```

### 2. Add Complementary Data Source

Place the following file:

```text
gdp.csv
```

inside:

```text
data/raw/extra/
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Pipeline Execution

### Phase 1 — Extract

```bash
python src/extract.py
```

Output:

```text
gdp_all.json
```

### Phase 2 — Transform

```bash
python src/transform.py
```

Operations:

- Data cleansing.
- Format standardization.
- Multi-source integration.
- Record deduplication.
- Derived metric generation.
- Data quality reporting.

Outputs:

```text
data/processed/silver/wdi_staging.csv
data/curated/gold/wdi_gold.csv
```

Report:

```text
data/logs/transform.log
```

### Phase 3 — Load

```bash
python src/load.py
```

Output:

```text
data/db/analytics_dw.db
```

---

## Dimensional Model

The Data Warehouse follows a **Star Schema** approach, enabling analysis by:

- Country
- Indicator
- Year
- Region
- Income Group

---

## Data Quality Controls

The pipeline includes validation mechanisms for:

- Missing values
- Duplicate records
- Referential integrity
- Chronological consistency
- Cross-source compatibility

Validation results are recorded in the project's log files.

---

## Generated Outputs

| Layer | File | Description |
|---------|---------|------------|
| Raw | gdp_all.json | Data extracted from the API |
| Silver | wdi_staging.csv | Cleaned and integrated dataset |
| Gold | wdi_gold.csv | Analysis-ready dataset |
| DW | analytics_dw.db | Analytical Data Warehouse |
| Logs | transform.log | Data quality report |
