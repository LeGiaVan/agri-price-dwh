import os
from datetime import UTC, datetime

import pandas as pd
import requests

try:
    from ingest.utils import (
        get_logger,
        motherduck_connection,
        parse_json_env,
        retry,
        write_dataframe,
    )
except ModuleNotFoundError:
    from utils import (
        get_logger,
        motherduck_connection,
        parse_json_env,
        retry,
        write_dataframe,
    )


API_TEMPLATE = (
    "https://api.worldbank.org/v2/en/country/WLD/indicator/{indicator}"
    "?format=json&per_page=20000&date={date_range}"
)
DEFAULT_DATE_RANGE = "2000M01:2025M12"
PINK_SHEET_URL = (
    "https://thedocs.worldbank.org/en/doc/"
    "74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/"
    "CMO-Historical-Data-Monthly.xlsx"
)

# Override this with WB_COMMODITY_SERIES when the exact World Bank commodity
# indicator codes are agreed by the team. Shape:
# {"rice": {"indicator": "...", "unit": "USD/mt"}, ...}
DEFAULT_SERIES = {
    "rice": {"indicator": "PRICENPQUSDM", "unit": "USD/mt"},
    "coffee": {"indicator": "PCOFFOTMUSDM", "unit": "USD/kg"},
    "rubber": {"indicator": "PRUBBUSDM", "unit": "USD/kg"},
}

LOG = get_logger("ingest.worldbank")


@retry(attempts=3, delay_seconds=10)
def fetch_indicator(indicator: str, date_range: str) -> list[dict]:
    url = API_TEMPLATE.format(indicator=indicator, date_range=date_range)
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    payload = response.json()

    if not isinstance(payload, list) or len(payload) < 2:
        LOG.warning(
            "Unexpected World Bank API response for indicator=%s: %s",
            indicator,
            str(payload)[:300],
        )
        return []

    metadata = payload[0] or {}
    rows = payload[1] or []
    if metadata.get("total") in (0, "0") or not rows:
        LOG.warning("World Bank returned no rows for indicator=%s", indicator)

    return rows


def normalize_worldbank() -> pd.DataFrame:
    series = parse_json_env("WB_COMMODITY_SERIES", DEFAULT_SERIES)
    date_range = os.getenv("WB_DATE_RANGE", DEFAULT_DATE_RANGE)
    frames: list[pd.DataFrame] = []

    for commodity, config in series.items():
        indicator = config["indicator"]
        unit = config.get("unit", "USD/kg")
        LOG.info(
            "Fetching World Bank commodity=%s indicator=%s date_range=%s",
            commodity,
            indicator,
            date_range,
        )
        rows = fetch_indicator(indicator, date_range)
        if not rows:
            continue

        frame = pd.DataFrame(rows)
        frame["commodity"] = commodity
        frame["indicator_code"] = indicator
        frame["indicator_name"] = frame.get("indicator", pd.Series(index=frame.index)).apply(
            lambda value: value.get("value") if isinstance(value, dict) else None
        )
        frame["price_date"] = parse_worldbank_dates(frame["date"])
        frame["price_usd"] = pd.to_numeric(frame["value"], errors="coerce")
        frame["region"] = "global"
        frame["country"] = "World"
        frame["currency"] = "USD"
        frame["unit"] = unit
        frame["source"] = "WORLD_BANK_API"
        frame["ingested_at"] = datetime.now(UTC).replace(tzinfo=None)
        frame["year"] = frame["price_date"].dt.year
        frame["month"] = frame["price_date"].dt.month
        frames.append(frame)

    if not frames:
        LOG.warning(
            "World Bank Indicators API returned no commodity rows; falling back to Pink Sheet monthly workbook"
        )
        return normalize_pink_sheet()

    normalized = pd.concat(frames, ignore_index=True)
    normalized = normalized[
        [
            "commodity",
            "price_date",
            "year",
            "month",
            "region",
            "country",
            "price_usd",
            "currency",
            "unit",
            "source",
            "indicator_code",
            "indicator_name",
            "ingested_at",
        ]
    ].dropna(subset=["commodity", "price_date", "price_usd"])

    return normalized.drop_duplicates(
        subset=["commodity", "price_date", "region", "source"], keep="last"
    )


def parse_worldbank_dates(values: pd.Series) -> pd.Series:
    clean = values.astype(str).str.replace(
        r"^(\d{4})M(\d{1,2})$",
        lambda match: f"{match.group(1)}-{int(match.group(2)):02d}-01",
        regex=True,
    )
    clean = clean.str.replace(
        r"^(\d{4})Q([1-4])$",
        lambda match: f"{match.group(1)}-{(int(match.group(2)) - 1) * 3 + 1:02d}-01",
        regex=True,
    )
    return pd.to_datetime(clean, errors="coerce")


def normalize_pink_sheet() -> pd.DataFrame:
    df = pd.read_excel(PINK_SHEET_URL, sheet_name="Monthly Prices", skiprows=4)
    df.columns = [str(column).strip() for column in df.columns]
    date_col = df.columns[0]

    column_map = {
        "rice": find_column(df.columns, ("rice, thai 5%", "rice, thailand 5%", "rice")),
        "coffee": find_column(df.columns, ("coffee, robusta", "coffee, arabica", "coffee")),
        "rubber": find_column(df.columns, ("rubber, tsr20", "rubber, rss3", "rubber")),
    }
    column_map = {
        commodity: column
        for commodity, column in column_map.items()
        if column is not None
    }

    if not column_map:
        raise ValueError("Could not find supported commodity columns in Pink Sheet workbook")

    LOG.info("Pink Sheet columns selected: %s", column_map)
    selected = df[[date_col] + list(column_map.values())].copy()
    selected = selected.rename(columns={date_col: "price_date"})
    melted = selected.melt(
        id_vars=["price_date"],
        var_name="indicator_name",
        value_name="price_usd",
    )
    reverse_map = {column: commodity for commodity, column in column_map.items()}
    melted["commodity"] = melted["indicator_name"].map(reverse_map)
    melted["price_date"] = parse_worldbank_dates(melted["price_date"])
    melted["price_usd"] = pd.to_numeric(melted["price_usd"], errors="coerce")
    melted["year"] = melted["price_date"].dt.year
    melted["month"] = melted["price_date"].dt.month
    melted["region"] = "global"
    melted["country"] = "World"
    melted["currency"] = "USD"
    melted["unit"] = melted["commodity"].map(
        {
            "rice": "USD/mt",
            "coffee": "USD/kg",
            "rubber": "USD/kg",
        }
    )
    melted["source"] = "WORLD_BANK"
    melted["indicator_code"] = "PINK_SHEET_MONTHLY"
    melted["ingested_at"] = datetime.now(UTC).replace(tzinfo=None)

    normalized = melted[
        [
            "commodity",
            "price_date",
            "year",
            "month",
            "region",
            "country",
            "price_usd",
            "currency",
            "unit",
            "source",
            "indicator_code",
            "indicator_name",
            "ingested_at",
        ]
    ].dropna(subset=["commodity", "price_date", "price_usd"])

    return normalized.drop_duplicates(
        subset=["commodity", "price_date", "region", "source"], keep="last"
    )


def find_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    lowered = {column.lower(): column for column in columns}
    for candidate in candidates:
        for lowered_column, original_column in lowered.items():
            if candidate in lowered_column:
                return original_column
    return None


def ingest_worldbank() -> int:
    LOG.info("Starting World Bank ingest")
    normalized = normalize_worldbank()
    LOG.info(
        "World Bank normalized rows=%s commodities=%s",
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
        "price_usd",
        "currency",
        "unit",
        "source",
        "indicator_code",
        "indicator_name",
        "ingested_at",
    ]
    column_types = {
        "commodity": "varchar",
        "price_date": "date",
        "year": "integer",
        "month": "integer",
        "region": "varchar",
        "country": "varchar",
        "price_usd": "double",
        "currency": "varchar",
        "unit": "varchar",
        "source": "varchar",
        "indicator_code": "varchar",
        "indicator_name": "varchar",
        "ingested_at": "timestamp",
    }
    create_sql = """
        create table if not exists bronze.wb_prices_raw (
            commodity varchar,
            price_date date,
            year integer,
            month integer,
            region varchar,
            country varchar,
            price_usd double,
            currency varchar,
            unit varchar,
            source varchar,
            indicator_code varchar,
            indicator_name varchar,
            ingested_at timestamp
        )
    """

    with motherduck_connection() as con:
        write_dataframe(
            con,
            normalized,
            "bronze.wb_prices_raw",
            create_sql,
            column_types,
            columns,
            LOG,
        )
        total = con.execute("select count(*) from bronze.wb_prices_raw").fetchone()[0]

    LOG.info(
        "World Bank ingest complete: inserted_or_replaced_rows=%s total_bronze_rows=%s timestamp=%s",
        len(normalized),
        total,
        datetime.now(UTC).isoformat(),
    )
    return len(normalized)


if __name__ == "__main__":
    try:
        ingest_worldbank()
    except Exception:
        LOG.exception("World Bank ingest failed")
        raise
