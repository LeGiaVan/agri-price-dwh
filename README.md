# 🌾 agri-price-dwh

> **Data Warehouse — Analysis & Forecasting of Vietnam Agricultural Prices**  
> Course: Data Warehouse & Integration | Team of 5 | 2025

[![Ingest Status](https://github.com/{ORG}/agri-price-dwh/actions/workflows/ingest.yml/badge.svg)](https://github.com/{ORG}/agri-price-dwh/actions)

---

## 📋 Overview

A system that collects, cleans, stores, and forecasts prices for **5 key agricultural export commodities of Vietnam**: rice, coffee, pepper, cashew, and rubber.

Architecture: **Medallion Architecture (Bronze → Silver → Gold)** built on MotherDuck + dbt + LSTM/ARIMA + Streamlit GenBI.

```text
World Bank API / Yahoo Finance
        │
        ▼ (GitHub Actions, Daily at midnight)
  ┌─────────────┐
  │   BRONZE    │  Raw, unmodified data
  └──────┬──────┘
         │ dbt
         ▼
  ┌─────────────┐
  │   SILVER    │  Cleaned and standardized
  └──────┬──────┘
         │ dbt
         ▼
  ┌─────────────┐
  │    GOLD     │  Kimball Star Schema + ML features
  └──────┬──────┘
         │
    ┌────┴────┐
    ▼         ▼
  LSTM      Streamlit
  ARIMA     + Groq GenBI
```

---

## 🗂️ Lean Directory Structure

```text
agri-price-dwh/
├── .github/workflows/
│   └── ingest.yml          # GitHub Actions auto-trigger at 00:00 VN
├── ingest/
│   ├── Dockerfile          # Lean Dockerfile for ingestion
│   ├── requirements.txt    # Ingest dependencies
│   ├── worldbank_ingest.py # World Bank API ingestion
│   ├── yf_ingest.py        # Yahoo Finance ingestion
│   ├── main.py             # Runs all real ingestion sources
│   └── utils.py            # Logger, retry helpers
├── dbt/
│   ├── Dockerfile          # Lean Dockerfile for dbt
│   ├── dbt_project.yml
│   ├── profiles.yml        # MotherDuck connections (ignored)
│   └── models/             # Bronze, Silver, Gold transformations
├── ml/
│   ├── notebooks/          # LSTM / ARIMA training notebooks
│   └── models/             # Compiled weights (.h5)
├── dashboard/
│   ├── Dockerfile          # Lean Dockerfile for Streamlit
│   ├── requirements.txt    # Dashboard dependencies
│   ├── app.py              # Main Streamlit app
│   └── genbi_chat.py       # Groq AI integration
├── scripts/
│   └── db_init.py          # MotherDuck DB initialization
├── docker-compose.yml      # Root docker-compose for all services
├── Makefile                # Standardized developer commands
├── .env.example            # Environment variables template
└── README.md
```

---

## ⚡ Quickstart (5 Minutes)

### 1. Clone the repository

```bash
git clone https://github.com/{ORG}/agri-price-dwh.git
cd agri-price-dwh
```

### 2. Set up Environment Variables

```bash
cp .env.example .env
```

Open `.env` and fill in your actual tokens:

```env
MOTHERDUCK_TOKEN=md_token_xxxxxxxxxxxxx
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxx
```

> 📌 **Where to get tokens?**
> - **MotherDuck**: [app.motherduck.com](https://app.motherduck.com) → Settings → Access Tokens
> - **Groq**: [console.groq.com](https://console.groq.com) → API Keys → Create

### 3. Initialize MotherDuck Database

Initialize the database schemas (`bronze`, `silver`, `gold`):

```bash
# Using Python locally:
pip install duckdb python-dotenv

# On Windows:
.\run.bat init-db

# On Linux/Mac:
make init-db
```

*Expected output:*
```text
✅ Connected to MotherDuck
✅ Schema bronze created
✅ Schema silver created
✅ Schema gold created
```

### 4. Run Services with Docker & Task Runner

We use a `Makefile` (for Linux/Mac) and `run.bat` (for Windows) to simplify Docker commands. **Ensure Docker is running on your machine.**

```bash
# 1. Run Master Data Ingestion (World Bank and Yahoo Finance)
.\run.bat ingest          # Windows
make ingest               # Linux/Mac

# 2. Run dbt Transformations (Bronze -> Silver -> Gold)
.\run.bat run-dbt         # Windows
make run-dbt              # Linux/Mac

# 3. Start the Streamlit Dashboard (accessible at http://localhost:8501)
.\run.bat run-dashboard   # Windows
make run-dashboard        # Linux/Mac

# 4. OR: Start EVERYTHING in the background at once
.\run.bat start-all       # Windows
make start-all            # Linux/Mac
```

---

## 🗄️ Data Model (Star Schema)

```text
                    ┌─────────────────┐
                    │  dim_commodity  │
                    │─────────────────│
                    │ commodity_id PK │
                    │ name_vi         │
                    │ name_en         │
                    │ category        │
                    └────────┬────────┘
                             │
┌───────────┐      ┌─────────▼──────────┐      ┌─────────────┐
│ dim_date  │      │  fact_price_daily  │      │ dim_region  │
│───────────│      │────────────────────│      │─────────────│
│ date_id PK├──────┤ price_id  PK       ├──────┤ region_id PK│
│ date      │      │ commodity_id  FK   │      │ country     │
│ year      │      │ date_id  FK        │      │ province    │
│ month     │      │ region_id  FK      │      │ market_name │
│ quarter   │      │ price_usd          │      └─────────────┘
│ is_harvest│      │ price_vnd          │
└───────────┘      │ price_change_pct   │
                   │ price_7d_avg       │
                   │ source             │
                   └────────────────────┘
```

---

## 🤖 AI/ML Pipeline

| Model | Library | Objective | Metrics |
|---|---|---|---|
| **ARIMA** | `pmdarima` | Baseline 30-day forecasting | RMSE, MAPE |
| **LSTM** | `TensorFlow/Keras` | Advanced forecasting | RMSE, MAPE |
| **SHAP** | `shap` | Feature importance explanation | — |

**Acceptance Threshold**: MAPE < 10% on the test set.

---

## 📊 Dashboard

The application features the following sections:

| Page | Content |
|---|---|
| **Overview** | Metric cards, historical price line charts |
| **Analysis** | Seasonality heatmaps, commodity comparisons, correlations |
| **Forecasting** | LSTM/ARIMA predictions with confidence intervals |
| **AI Assistant** | Vietnamese-supported GenBI chat powered by Groq Llama 3 |

---

## 👥 Team Roles

| Member | Role | Working Branch |
|---|---|---|
| Team Leader | Infrastructure, Architecture | `main` |
| Member 1 | Data Ingestion | `feature/ingest-pipeline` |
| Member 2 | dbt Transformation | `feature/dbt-silver-gold` |
| Member 3 | ML Engineering | `feature/ml-forecasting` |
| Member 4 | Dashboard & GenBI | `feature/dashboard-genbi` |

---

## 🔧 Useful dbt Commands

If you choose to run dbt locally instead of via Docker:

```bash
cd dbt

# Test connection
dbt debug

# Run all models
dbt run

# Run specific layers
dbt run --select silver
dbt run --select gold

# Run tests
dbt test

# Generate and serve documentation locally
dbt docs generate && dbt docs serve
```

---

## 🚀 GitHub Actions

The `ingest.yml` workflow is scheduled to run automatically at **00:00 VN Time** every day.

To trigger it manually: Go to the GitHub repository → **Actions** tab → **Daily Ingest** → **Run workflow**.

---

## ❓ FAQ & Support

Encountering issues? Open an **Issue** on GitHub.  
For more details on the team's workflow, refer to [CONTRIBUTING.md](./CONTRIBUTING.md).

---

## Monthly GitHub Actions Runbook

The `.github/workflows/ingest.yml` workflow runs on the first day of each month at `17:00 UTC`, which is `00:00` the next day in Vietnam time (`Asia/Bangkok`). It can also be started manually from the GitHub **Actions** tab.

Required GitHub repository secrets:

```text
MOTHERDUCK_TOKEN
```

What the workflow does:

1. Installs Python, ingest dependencies, and `dbt-duckdb`.
2. Runs `python ingest/daily_cron.py`.
3. Upserts Yahoo Finance commodity futures into `bronze.yf_prices_raw`.
4. Runs the monthly World Bank ingest with duplicate protection.
5. Runs `dbt seed` and `dbt build` from the `dbt/` project.

Supported Yahoo futures in the cron job:

| Commodity | Yahoo ticker | Raw quote unit | Normalized unit |
|---|---|---|---|
| coffee | `KC=F` | cents/lb | USD/kg |
| cocoa | `CC=F` | USD/metric ton | USD/kg |
| cotton | `CT=F` | cents/lb | USD/kg |
| rice | `ZR=F` | cents/cwt | USD/kg |

Manual rerun examples:

```bash
python ingest/daily_cron.py
python ingest/daily_cron.py --start-date 2026-01-01 --end-date 2026-02-01
python ingest/daily_cron.py --dry-run
dbt seed --project-dir dbt --profiles-dir dbt
dbt build --project-dir dbt --profiles-dir dbt
```

Debug checklist:

- If ingest fails before dbt starts, check the uploaded `logs/` artifact.
- If Yahoo returns no new rows, the workflow exits successfully and logs a warning.
- If one Yahoo ticker fails, the other tickers are still written.
- If `dbt build` fails, bronze data is kept and the workflow reports failure.
- Confirm `MOTHERDUCK_TOKEN` can write to the `agri_dwh` database.
