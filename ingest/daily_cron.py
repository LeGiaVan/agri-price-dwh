import argparse
import logging
import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from ingest.utils import get_logger, motherduck_connection, retry
    from ingest.worldbank_ingest import ingest_worldbank
except ImportError:
    from utils import get_logger, motherduck_connection, retry
    from worldbank_ingest import ingest_worldbank


LOG = get_logger("ingest.daily_cron")

SOURCE = "YAHOO_FINANCE"
REGION = "US futures market"
COUNTRY = "United States"
LB_TO_KG = 0.45359237
CWT_TO_KG = 45.359237

YAHOO_CONTRACTS = {
    "KC=F": {
        "commodity": "coffee",
        "raw_unit": "cents/lb",
        "price_usd_per_kg": lambda close: (close / 100.0) / LB_TO_KG,
    },
    "CC=F": {
        "commodity": "cocoa",
        "raw_unit": "usd/metric_ton",
        "price_usd_per_kg": lambda close: close / 1000.0,
    },
    "CT=F": {
        "commodity": "cotton",
        "raw_unit": "cents/lb",
        "price_usd_per_kg": lambda close: (close / 100.0) / LB_TO_KG,
    },
    "ZR=F": {
        "commodity": "rice",
        "raw_unit": "cents/cwt",
        "price_usd_per_kg": lambda close: (close / 100.0) / CWT_TO_KG,
    },
}


def _create_yahoo_table(con) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS bronze.yf_prices_raw (
            price_date DATE,
            price_usd DOUBLE,
            price_usd_per_kg DOUBLE,
            commodity VARCHAR,
            source VARCHAR,
            ticker VARCHAR,
            raw_unit VARCHAR,
            currency VARCHAR,
            region VARCHAR,
            country VARCHAR,
            ingested_at TIMESTAMP
        )
        """
    )

    for column, data_type in {
        "price_usd_per_kg": "DOUBLE",
        "ticker": "VARCHAR",
        "raw_unit": "VARCHAR",
        "currency": "VARCHAR",
        "region": "VARCHAR",
        "country": "VARCHAR",
        "ingested_at": "TIMESTAMP",
    }.items():
        con.execute(f"ALTER TABLE bronze.yf_prices_raw ADD COLUMN IF NOT EXISTS {column} {data_type}")


def _max_yahoo_date(con) -> date | None:
    try:
        value = con.execute(
            """
            SELECT max(try_cast(price_date AS DATE))
            FROM bronze.yf_prices_raw
            WHERE source = ?
            """,
            [SOURCE],
        ).fetchone()[0]
    except Exception:
        return None
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def _date_range(args: argparse.Namespace, con) -> tuple[date, date]:
    tz = ZoneInfo(args.timezone)
    today = datetime.now(tz).date()

    if args.start_date:
        start = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    else:
        max_date = _max_yahoo_date(con)
        start = max_date + timedelta(days=1) if max_date else today - timedelta(days=args.lookback_days)

    if args.end_date:
        end = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    else:
        end = today + timedelta(days=1)

    return start, end


def _close_series(df: pd.DataFrame, ticker: str) -> pd.Series:
    if isinstance(df.columns, pd.MultiIndex):
        if ("Close", ticker) in df.columns:
            return df[("Close", ticker)]
        close = df.xs("Close", level=0, axis=1)
        return close.iloc[:, 0]
    return df["Close"]


@retry(attempts=3, delay_seconds=10, retry_exceptions=(Exception,))
def _download_ticker(ticker: str, start: date, end: date) -> pd.DataFrame:
    return yf.download(
        ticker,
        start=start.isoformat(),
        end=end.isoformat(),
        interval="1d",
        progress=False,
        auto_adjust=False,
    )


def _fetch_yahoo_prices(start: date, end: date, tickers: list[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    for ticker in tickers:
        config = YAHOO_CONTRACTS[ticker]
        commodity = config["commodity"]
        try:
            LOG.info("Fetching %s (%s) from %s to %s", commodity, ticker, start, end)
            raw = _download_ticker(ticker, start, end)
            if raw.empty:
                LOG.warning("No Yahoo rows returned for %s (%s)", commodity, ticker)
                continue

            close = _close_series(raw, ticker).dropna()
            if close.empty:
                LOG.warning("No close prices returned for %s (%s)", commodity, ticker)
                continue

            df = close.reset_index()
            df.columns = ["price_date", "price_usd"]
            df["price_date"] = pd.to_datetime(df["price_date"]).dt.date
            df["price_usd"] = pd.to_numeric(df["price_usd"], errors="coerce")
            df = df.dropna(subset=["price_usd"])
            df["price_usd_per_kg"] = df["price_usd"].map(config["price_usd_per_kg"])
            df["commodity"] = commodity
            df["source"] = SOURCE
            df["ticker"] = ticker
            df["raw_unit"] = config["raw_unit"]
            df["currency"] = "USD"
            df["region"] = REGION
            df["country"] = COUNTRY
            df["ingested_at"] = datetime.utcnow()
            frames.append(df)
            LOG.info("Prepared %s rows for %s", len(df), ticker)
        except Exception as exc:
            LOG.exception("Ticker %s failed; continuing with other tickers: %s", ticker, exc)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _upsert_yahoo_prices(con, df: pd.DataFrame, dry_run: bool) -> int:
    columns = [
        "price_date",
        "price_usd",
        "price_usd_per_kg",
        "commodity",
        "source",
        "ticker",
        "raw_unit",
        "currency",
        "region",
        "country",
        "ingested_at",
    ]
    df = df[columns].copy()

    if dry_run:
        LOG.info("Dry run enabled; would upsert %s Yahoo rows", len(df))
        return len(df)

    con.register("incoming_yahoo_prices", df)
    con.execute(
        """
        DELETE FROM bronze.yf_prices_raw
        WHERE (try_cast(price_date AS DATE), commodity, region, source) IN (
            SELECT price_date, commodity, region, source
            FROM incoming_yahoo_prices
        )
        """
    )
    con.execute(
        f"""
        INSERT INTO bronze.yf_prices_raw ({", ".join(columns)})
        SELECT {", ".join(columns)}
        FROM incoming_yahoo_prices
        """
    )
    con.unregister("incoming_yahoo_prices")
    LOG.info("Upserted %s Yahoo rows into bronze.yf_prices_raw", len(df))
    return len(df)


def _run_worldbank(dry_run: bool) -> None:
    if dry_run:
        LOG.info("Dry run enabled; skipping World Bank ingest")
        return
    try:
        LOG.info("Running monthly World Bank ingest")
        ingest_worldbank()
    except Exception as exc:
        LOG.exception("World Bank ingest failed; Yahoo partial success is kept: %s", exc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monthly incremental ingest for GitHub Actions.")
    parser.add_argument("--start-date", help="Inclusive start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", help="Exclusive end date in YYYY-MM-DD format.")
    parser.add_argument("--timezone", default="Asia/Bangkok")
    parser.add_argument("--lookback-days", type=int, default=45)
    parser.add_argument("--tickers", nargs="*", default=list(YAHOO_CONTRACTS))
    parser.add_argument("--skip-worldbank", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    unknown = sorted(set(args.tickers) - set(YAHOO_CONTRACTS))
    if unknown:
        raise ValueError(f"Unsupported Yahoo tickers: {', '.join(unknown)}")

    con = motherduck_connection()
    try:
        _create_yahoo_table(con)
        start, end = _date_range(args, con)
        if start >= end:
            LOG.warning("No new Yahoo date range to fetch: start=%s end=%s", start, end)
        else:
            yahoo_prices = _fetch_yahoo_prices(start, end, args.tickers)
            if yahoo_prices.empty:
                LOG.warning("Yahoo returned no new rows; exiting successfully")
            else:
                _upsert_yahoo_prices(con, yahoo_prices, args.dry_run)

        if not args.skip_worldbank:
            _run_worldbank(args.dry_run)
    finally:
        con.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
