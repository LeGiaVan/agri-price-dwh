import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.metrics import mean_absolute_error, mean_squared_error


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = PROJECT_ROOT / "ml" / "models"
REPORT_PATH = PROJECT_ROOT / "ml" / "model_evaluation.md"
COMMODITIES = ["rice", "coffee", "rubber"]


def load_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()


def motherduck_connection() -> duckdb.DuckDBPyConnection:
    load_env()
    token = os.getenv("MOTHERDUCK_TOKEN")
    database = os.getenv("MOTHERDUCK_DB", "agri_dwh")
    if not token:
        raise RuntimeError("MOTHERDUCK_TOKEN is missing")
    return duckdb.connect(f"md:{database}?motherduck_token={token}")


def load_ml_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    commodities_sql = ", ".join(f"'{commodity}'" for commodity in COMMODITIES)
    df = con.execute(
        f"""
        select *
        from gold.gold_ml_features
        where commodity in ({commodities_sql})
        order by commodity, price_date
        """
    ).fetchdf()
    if df.empty:
        raise RuntimeError("gold.gold_ml_features returned no rows for rice, coffee, pepper")
    df["price_date"] = pd.to_datetime(df["price_date"])
    return df


def prepare_supervised_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["commodity", "price_date"]).copy()
    df["target_price"] = df.groupby("commodity")["price_usd_per_kg"].shift(-1)
    df = df.dropna(subset=["price_usd_per_kg", "target_price"])

    parts = []
    for commodity, group in df.groupby("commodity"):
        group = group.sort_values("price_date").copy()
        train = group[group["price_date"] < "2023-01-01"]
        reference = train if not train.empty else group
        lower = reference["price_usd_per_kg"].quantile(0.01)
        upper = reference["price_usd_per_kg"].quantile(0.99)
        group["is_outlier"] = (
            (group["price_usd_per_kg"] < lower) | (group["price_usd_per_kg"] > upper)
        ).astype(int)
        group["price_clean"] = group["price_usd_per_kg"].clip(lower, upper)
        parts.append(group)

    return pd.concat(parts, ignore_index=True)


def train_test_split_by_time(group: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = group[group["price_date"] < "2023-01-01"].copy()
    test = group[
        (group["price_date"] >= "2023-01-01") & (group["price_date"] < "2025-01-01")
    ].copy()
    if train.empty or test.empty:
        split_idx = max(1, int(len(group) * 0.8))
        train = group.iloc[:split_idx].copy()
        test = group.iloc[split_idx:].copy()
    return train, test


def train_val_test_split_by_time(
    group: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = group[group["price_date"] < "2023-01-01"].copy()
    val = group[
        (group["price_date"] >= "2023-01-01") & (group["price_date"] < "2024-01-01")
    ].copy()
    test = group[
        (group["price_date"] >= "2024-01-01") & (group["price_date"] < "2025-01-01")
    ].copy()
    if train.empty or val.empty or test.empty:
        n = len(group)
        train_end = max(1, int(n * 0.7))
        val_end = max(train_end + 1, int(n * 0.85))
        train = group.iloc[:train_end].copy()
        val = group.iloc[train_end:val_end].copy()
        test = group.iloc[val_end:].copy()
    return train, val, test


def mape(y_true, y_pred) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = y_true != 0
    if not mask.any():
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def metric_row(model: str, commodity: str, y_true, y_pred, **extra) -> dict:
    row = {
        "model": model,
        "commodity": commodity,
        "rmse": float(mean_squared_error(y_true, y_pred, squared=False)),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "mape": mape(y_true, y_pred),
    }
    row.update(extra)
    return row


def ensure_gold_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("create schema if not exists gold")
    con.execute(
        """
        create table if not exists gold.forecast_arima (
            date date,
            commodity varchar,
            predicted_price double,
            model_name varchar,
            model_order varchar,
            adf_pvalue double,
            created_at timestamp
        )
        """
    )
    con.execute(
        """
        create table if not exists gold.forecast_lstm (
            date date,
            commodity varchar,
            predicted_price double,
            confidence_interval_lower double,
            confidence_interval_upper double,
            model_name varchar,
            created_at timestamp
        )
        """
    )
    con.execute(
        """
        create table if not exists gold.model_metrics (
            model varchar,
            commodity varchar,
            rmse double,
            mae double,
            mape double,
            extra varchar,
            created_at timestamp
        )
        """
    )
    con.execute(
        """
        create table if not exists gold.fact_forecasts (
            forecast_date date,
            commodity varchar,
            predicted_price double,
            model_name varchar,
            created_at timestamp
        )
        """
    )


def replace_forecast(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    df: pd.DataFrame,
    model_name: str,
) -> None:
    if df.empty:
        return
    con.register("forecast_rows", df)
    con.execute(f"delete from {table_name} where model_name = ?", [model_name])
    con.execute(f"insert into {table_name} select * from forecast_rows")
    con.unregister("forecast_rows")


def replace_metrics(con: duckdb.DuckDBPyConnection, rows: list[dict], models: list[str]) -> None:
    if not rows:
        return
    metrics_df = pd.DataFrame(rows)
    metrics_df["extra"] = metrics_df.get("extra", "")
    metrics_df["created_at"] = pd.Timestamp.utcnow()
    metrics_df = metrics_df[["model", "commodity", "rmse", "mae", "mape", "extra", "created_at"]]
    con.register("metric_rows", metrics_df)
    placeholders = ", ".join("?" for _ in models)
    con.execute(f"delete from gold.model_metrics where model in ({placeholders})", models)
    con.execute("insert into gold.model_metrics select * from metric_rows")
    con.unregister("metric_rows")


def write_evaluation_report(rows: list[dict]) -> None:
    if not rows:
        return
    report_df = pd.DataFrame(rows)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", encoding="utf-8") as f:
        f.write("# Model Evaluation\n\n")
        f.write("Metrics are calculated on the time-based holdout split.\n\n")
        f.write(report_df.to_markdown(index=False))
        f.write("\n")
