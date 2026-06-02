import json
import logging
import os
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Iterable

import duckdb
import pandas as pd
import requests
from dotenv import load_dotenv


load_dotenv()

LOG_DIR = Path(os.getenv("INGEST_LOG_DIR", "logs"))
ERROR_LOG_PATH = LOG_DIR / "ingest_error.log"


def get_logger(name: str) -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)

        file_handler = logging.FileHandler(ERROR_LOG_PATH, encoding="utf-8")
        file_handler.setFormatter(formatter)

        logger.addHandler(stream_handler)
        logger.addHandler(file_handler)

    return logger


def retry(
    attempts: int = 3,
    delay_seconds: int = 5,
    retry_exceptions: tuple[type[BaseException], ...] = (
        requests.Timeout,
        requests.ConnectionError,
        TimeoutError,
    ),
) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error: BaseException | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retry_exceptions as exc:
                    last_error = exc
                    if attempt == attempts:
                        break
                    time.sleep(delay_seconds * attempt)
            if last_error is not None:
                raise last_error
            return func(*args, **kwargs)

        return wrapper

    return decorator


def motherduck_connection() -> duckdb.DuckDBPyConnection:
    database = os.getenv("MOTHERDUCK_DATABASE") or os.getenv("MOTHERDUCK_DB", "agri_dwh")
    token = os.getenv("MOTHERDUCK_TOKEN")
    connection_string = f"md:{database}"
    if token:
        connection_string = f"{connection_string}?motherduck_token={token}"
    con = duckdb.connect(connection_string)
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    return con


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().lower()


def first_existing_column(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    normalized = {column.lower().strip(): column for column in columns}
    for candidate in candidates:
        found = normalized.get(candidate.lower().strip())
        if found:
            return found
    return None


def parse_json_env(name: str, default: Any) -> Any:
    raw = os.getenv(name)
    if not raw:
        return default
    return json.loads(raw)


def write_dataframe(
    con: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    table_name: str,
    create_sql: str,
    column_types: dict[str, str],
    insert_columns: list[str],
    logger: logging.Logger,
) -> None:
    if df.empty:
        logger.warning("No rows to insert into %s", table_name)
        return

    con.execute(create_sql)
    for column, data_type in column_types.items():
        con.execute(f"alter table {table_name} add column if not exists {column} {data_type}")

    con.register("incoming_prices", df[insert_columns])
    con.execute(
        f"""
        delete from {table_name}
        where (commodity, price_date, region, source) in (
            select commodity, price_date, region, source from incoming_prices
        )
        """
    )
    con.execute(
        f"""
        insert into {table_name} ({", ".join(insert_columns)})
        select {", ".join(insert_columns)}
        from incoming_prices
        """
    )
    con.unregister("incoming_prices")
