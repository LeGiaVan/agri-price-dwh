import os
from datetime import UTC, datetime

import pandas as pd
from datasets import DatasetDict, load_dataset

try:
    from ingest.utils import (
        first_existing_column,
        get_logger,
        motherduck_connection,
        normalize_text,
        retry,
        write_dataframe,
    )
except ModuleNotFoundError:
    from utils import (
        first_existing_column,
        get_logger,
        motherduck_connection,
        normalize_text,
        retry,
        write_dataframe,
    )


DATASET_NAME = "electricsheepasia/asia-faostat-producer-prices-pp"
TARGET_KEYWORDS = {
    "rice": ("rice", "paddy", "gao", "lua"),
    "coffee": ("coffee", "arabica", "robusta", "ca phe"),
    "pepper": ("pepper", "black pepper", "white pepper", "ho tieu"),
    "cashew": ("cashew", "cashew nut", "dieu"),
    "rubber": ("rubber", "natural rubber", "cao su"),
}

LOG = get_logger("ingest.fao")


@retry(attempts=3, delay_seconds=10, retry_exceptions=(Exception,))
def load_fao_dataframe() -> pd.DataFrame:
    dataset = load_dataset(DATASET_NAME, token=os.getenv("HF_TOKEN"))
    if isinstance(dataset, DatasetDict):
        split_name = "train" if "train" in dataset else next(iter(dataset.keys()))
        LOG.info("Loaded HuggingFace dataset=%s split=%s", DATASET_NAME, split_name)
        return dataset[split_name].to_pandas()

    LOG.info("Loaded HuggingFace dataset=%s", DATASET_NAME)
    return dataset.to_pandas()


def map_commodity(value: object) -> str | None:
    text = normalize_text(value)
    for commodity, keywords in TARGET_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return commodity
    return None


def normalize_fao(df: pd.DataFrame) -> pd.DataFrame:
    # 1. Filter to Viet Nam only
    df_vn = df[df["Area"] == "Viet Nam"].copy()

    if df_vn.empty:
        LOG.warning("No Viet Nam data found in dataset")
        return pd.DataFrame()

    # 2. Compute yearly exchange rate from annual values
    annual_usd = df_vn[
        (df_vn["Element"] == "Producer Price (USD/tonne)") & 
        (df_vn["Months"] == "Annual value")
    ][["Year", "Item", "Value"]].rename(columns={"Value": "price_usd"})

    annual_lcu = df_vn[
        (df_vn["Element"] == "Producer Price (LCU/tonne)") & 
        (df_vn["Months"] == "Annual value")
    ][["Year", "Item", "Value"]].rename(columns={"Value": "price_lcu"})

    # Join to find the exchange rate for each year and commodity
    rates = pd.merge(annual_usd, annual_lcu, on=["Year", "Item"])
    rates["rate"] = rates["price_lcu"] / rates["price_usd"]

    # Group by Year to get the average exchange rate for Viet Nam in that year
    yearly_rates = rates.groupby("Year")["rate"].mean().reset_index()

    # 3. Extract monthly LCU prices
    monthly_lcu = df_vn[
        (df_vn["Element"] == "Producer Price (LCU/tonne)") & 
        (df_vn["Months"] != "Annual value")
    ].copy()

    # Join with yearly exchange rates
    working = pd.merge(monthly_lcu, yearly_rates, on="Year", how="left")

    # Convert LCU/tonne to USD/tonne: price_usd = price_lcu / rate
    # If rate is missing for some reason, use a fallback (e.g. 23000 VND/USD)
    working["rate"] = working["rate"].fillna(23000.0)
    working["price_usd_per_kg"] = (working["Value"] / working["rate"]) / 1000.0

    # Map months to numbers
    month_map = {
        "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
        "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12
    }
    working["month"] = working["Months"].map(month_map)
    working["year"] = working["Year"]

    # Map commodities
    working["commodity"] = working["Item"].map(map_commodity)
    working = working[working["commodity"].notna()].copy()

    # Create price_date
    working["price_date"] = pd.to_datetime(
        {"year": working["year"], "month": working["month"].fillna(1), "day": 1},
        errors="coerce",
    )

    # Set region mapping based on typical production regions in Viet Nam
    region_map = {
        "rice": "Mekong Delta",
        "coffee": "Central Highlands",
        "pepper": "South East",
        "cashew": "South East",
        "rubber": "South East"
    }
    working["region"] = working["commodity"].map(region_map).fillna("unknown")

    # Final metadata columns
    working["country"] = "Vietnam"
    working["currency"] = "USD"
    working["unit"] = "kg"
    working["source"] = "FAO_HUGGINGFACE"
    working["dataset_name"] = DATASET_NAME
    working["original_commodity"] = working["Item"].astype(str)
    working["ingested_at"] = datetime.now(UTC).replace(tzinfo=None)

    normalized = working[
        [
            "commodity",
            "price_date",
            "year",
            "month",
            "region",
            "country",
            "price_usd_per_kg",
            "currency",
            "unit",
            "source",
            "dataset_name",
            "original_commodity",
            "ingested_at",
        ]
    ].dropna(subset=["commodity", "price_date", "price_usd_per_kg"])

    return normalized.drop_duplicates(
        subset=["commodity", "price_date", "region", "source"], keep="last"
    )


def ingest_fao() -> int:
    LOG.info("Starting FAO ingest: dataset=%s", DATASET_NAME)
    raw = load_fao_dataframe()
    normalized = normalize_fao(raw)
    LOG.info(
        "FAO normalized rows=%s commodities=%s",
        len(normalized),
        sorted(normalized["commodity"].unique().tolist()) if not normalized.empty else [],
    )

    columns = [
        "commodity",
        "price_date",
        "year",
        "month",
        "region",
        "country",
        "price_usd_per_kg",
        "currency",
        "unit",
        "source",
        "dataset_name",
        "original_commodity",
        "ingested_at",
    ]
    column_types = {
        "commodity": "varchar",
        "price_date": "date",
        "year": "integer",
        "month": "integer",
        "region": "varchar",
        "country": "varchar",
        "price_usd_per_kg": "double",
        "currency": "varchar",
        "unit": "varchar",
        "source": "varchar",
        "dataset_name": "varchar",
        "original_commodity": "varchar",
        "ingested_at": "timestamp",
    }
    create_sql = """
        create table if not exists bronze.fao_prices_raw (
            commodity varchar,
            price_date date,
            year integer,
            month integer,
            region varchar,
            country varchar,
            price_usd_per_kg double,
            currency varchar,
            unit varchar,
            source varchar,
            dataset_name varchar,
            original_commodity varchar,
            ingested_at timestamp
        )
    """

    with motherduck_connection() as con:
        write_dataframe(
            con,
            normalized,
            "bronze.fao_prices_raw",
            create_sql,
            column_types,
            columns,
            LOG,
        )
        total = con.execute("select count(*) from bronze.fao_prices_raw").fetchone()[0]

    LOG.info(
        "FAO ingest complete: inserted_or_replaced_rows=%s total_bronze_rows=%s timestamp=%s dataset=%s",
        len(normalized),
        total,
        datetime.now(UTC).isoformat(),
        DATASET_NAME,
    )
    return len(normalized)


if __name__ == "__main__":
    try:
        ingest_fao()
    except Exception:
        LOG.exception("FAO ingest failed")
        raise
