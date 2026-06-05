import pandas as pd
from pmdarima import auto_arima
from statsmodels.tsa.stattools import adfuller

from ml.common import (
    COMMODITIES,
    ensure_gold_tables,
    load_ml_features,
    metric_row,
    motherduck_connection,
    prepare_supervised_frame,
    replace_forecast,
    replace_metrics,
    train_test_split_by_time,
    write_evaluation_report,
)


def main() -> None:
    con = motherduck_connection()
    ensure_gold_tables(con)
    df = prepare_supervised_frame(load_ml_features(con))

    metrics = []
    forecast_rows = []

    for commodity in COMMODITIES:
        group = df[df["commodity"] == commodity].sort_values("price_date").copy()
        if len(group) < 12:
            print(f"Skipping {commodity}: not enough rows ({len(group)})")
            continue

        train, test = train_test_split_by_time(group)
        if test.empty:
            print(f"Skipping {commodity}: empty test split")
            continue

        y_train = train["price_clean"].astype(float)
        y_test = test["target_price"].astype(float)

        adf_pvalue = None
        try:
            adf_pvalue = float(adfuller(y_train.dropna())[1])
        except Exception as exc:
            print(f"ADF failed for {commodity}: {exc}")

        model = auto_arima(
            y_train,
            seasonal=False,
            stepwise=True,
            suppress_warnings=True,
            error_action="ignore",
            trace=False,
        )
        pred = model.predict(n_periods=len(test))

        metrics.append(
            metric_row(
                "ARIMA",
                commodity,
                y_test,
                pred,
                extra=f"order={model.order};adf_pvalue={adf_pvalue}",
            )
        )

        if "price_lag_1" in test.columns and test["price_lag_1"].notna().any():
            naive = test["price_lag_1"].fillna(method="ffill").fillna(y_train.iloc[-1])
            metrics.append(metric_row("Naive", commodity, y_test, naive, extra="price_lag_1"))

        for date, value in zip(test["price_date"], pred):
            forecast_rows.append(
                {
                    "date": pd.to_datetime(date).date(),
                    "commodity": commodity,
                    "predicted_price": float(value),
                    "model_name": "ARIMA",
                    "model_order": str(model.order),
                    "adf_pvalue": adf_pvalue,
                    "created_at": pd.Timestamp.utcnow(),
                }
            )

        print(f"Trained ARIMA for {commodity}: order={model.order}, rows={len(test)}")

    forecast_df = pd.DataFrame(forecast_rows)
    replace_forecast(con, "gold.forecast_arima", forecast_df, "ARIMA")
    replace_metrics(con, metrics, ["ARIMA", "Naive"])
    write_evaluation_report(metrics)
    con.close()
    print("ARIMA baseline complete")


if __name__ == "__main__":
    main()
