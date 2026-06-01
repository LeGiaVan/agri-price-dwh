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


DATASET_NAME = "mrm8488/fao-agricultural-market"
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
    commodity_col = first_existing_column(
        df.columns,
        ("commodity", "item", "item_name", "product", "product_name", "name"),
    )
    price_col = first_existing_column(
        df.columns,
        ("price_usd_per_kg", "price_usd", "price", "value", "market_price"),
    )
    date_col = first_existing_column(
        df.columns,
        ("price_date", "date", "period", "year_month", "month_date"),
    )
    year_col = first_existing_column(df.columns, ("year", "yr"))
    month_col = first_existing_column(df.columns, ("month", "month_number", "mo"))
    region_col = first_existing_column(
        df.columns,
        ("region", "market", "market_name", "area", "province"),
    )
    country_col = first_existing_column(df.columns, ("country", "country_name", "area_name"))
    currency_col = first_existing_column(df.columns, ("currency", "currency_code"))
    unit_col = first_existing_column(df.columns, ("unit", "price_unit", "measurement_unit"))

    if commodity_col is None or price_col is None:
        raise ValueError(
            "FAO dataset must contain a commodity column and a price/value column"
        )

    working = df.copy()
    working["commodity"] = working[commodity_col].map(map_commodity)
    working = working[working["commodity"].notna()].copy()

    if date_col:
        working["price_date"] = pd.to_datetime(working[date_col], errors="coerce")
    elif year_col:
        year = pd.to_numeric(working[year_col], errors="coerce")
        month = pd.to_numeric(working[month_col], errors="coerce") if month_col else 1
        if not isinstance(month, pd.Series):
            month = pd.Series([month] * len(working), index=working.index)
        working["price_date"] = pd.to_datetime(
            {"year": year, "month": month.fillna(1), "day": 1},
            errors="coerce",
        )
    else:
        raise ValueError("FAO dataset must contain a date column or year/month columns")

    working["price_usd_per_kg"] = pd.to_numeric(working[price_col], errors="coerce")
    working["region"] = working[region_col].fillna("unknown") if region_col else "unknown"
    working["country"] = working[country_col].fillna("Vietnam") if country_col else "Vietnam"
    working["currency"] = (
        working[currency_col].fillna("USD").astype(str).str.upper()
        if currency_col
        else "USD"
    )
    working["unit"] = working[unit_col].fillna("kg") if unit_col else "kg"
    working["source"] = "FAO_HUGGINGFACE"
    working["dataset_name"] = DATASET_NAME
    working["original_commodity"] = working[commodity_col].astype(str)
    working["ingested_at"] = datetime.now(UTC).replace(tzinfo=None)
    working["year"] = working["price_date"].dt.year
    working["month"] = working["price_date"].dt.month

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
