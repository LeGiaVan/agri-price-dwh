# DBT transformation

This project builds the Silver and Gold layers for the agricultural commodity price warehouse.

## Local setup

Install the dbt dependencies from the repository virtual environment:

```powershell
cd D:\UIUX\datawarehouse\dbt
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create `D:\UIUX\datawarehouse\.env` with at least:

```env
MOTHERDUCK_TOKEN=your_token
MOTHERDUCK_DB=agri_dwh
```

Use the helper script so dbt loads `.env` and keeps DuckDB/MotherDuck cache files inside the workspace:

```powershell
.\run_dbt.bat debug
.\run_dbt.bat parse
.\run_dbt.bat seed
.\run_dbt.bat run --select silver
.\run_dbt.bat test --select silver
.\run_dbt.bat run --select gold
.\run_dbt.bat test --select gold
```

## Expected Bronze contract

The Silver models expect raw source tables in MotherDuck:

- `bronze.wb_prices_raw`
- `bronze.yf_prices_raw`

The models can tolerate several common column names, but ingestion should ideally provide:

- `commodity`
- `date` or `year` and `month`
- `region`
- `country`
- `price`
- `currency`
- `unit`
- `ingested_at`

Final Gold output for ML and dashboard users is `gold.gold_ml_features`.
