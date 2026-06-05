import json

import numpy as np
import pandas as pd
import shap
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.models import Sequential

from ml.common import (
    COMMODITIES,
    MODEL_DIR,
    ensure_gold_tables,
    load_ml_features,
    metric_row,
    motherduck_connection,
    prepare_supervised_frame,
    replace_forecast,
    replace_metrics,
    train_val_test_split_by_time,
)


WINDOW = 30
FEATURE_COLS = [
    "price_clean",
    "price_change_pct",
    "price_7d_avg",
    "price_30d_avg",
    "price_90d_avg",
    "price_30d_volatility",
    "price_lag_1",
    "price_lag_7",
    "price_lag_30",
    "month",
    "quarter",
    "week",
    "is_weekend",
    "is_vietnam_public_holiday",
    "is_harvest_season",
    "source_count",
    "is_outlier",
]


def make_sequences(X, y, dates, window=WINDOW):
    X_seq, y_seq, date_seq = [], [], []
    for i in range(window, len(X)):
        X_seq.append(X[i - window : i])
        y_seq.append(y.iloc[i])
        date_seq.append(dates.iloc[i])
    return np.asarray(X_seq), np.asarray(y_seq, dtype=float), np.asarray(date_seq)


def build_model(feature_count: int) -> Sequential:
    model = Sequential(
        [
            LSTM(64, return_sequences=True, input_shape=(WINDOW, feature_count)),
            Dropout(0.2),
            LSTM(32),
            Dense(1),
        ]
    )
    model.compile(optimizer="adam", loss="mse")
    return model


def shap_importance(model, X_train_seq, X_test_seq, feature_cols):
    if len(X_train_seq) == 0 or len(X_test_seq) == 0:
        return {}
    background = X_train_seq[: min(100, len(X_train_seq))]
    sample = X_test_seq[: min(50, len(X_test_seq))]
    try:
        explainer = shap.DeepExplainer(model, background)
        values = explainer.shap_values(sample)
        shap_array = values[0] if isinstance(values, list) else values
        importance = np.abs(shap_array).mean(axis=(0, 1))
        return {
            feature: float(score)
            for feature, score in sorted(
                zip(feature_cols, importance), key=lambda item: item[1], reverse=True
            )
        }
    except Exception as exc:
        print(f"SHAP failed: {exc}")
        return {}


def main() -> None:
    con = motherduck_connection()
    ensure_gold_tables(con)
    df = prepare_supervised_frame(load_ml_features(con))
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    metrics = []
    forecast_rows = []

    for commodity in COMMODITIES:
        group = df[df["commodity"] == commodity].sort_values("price_date").copy()
        available_cols = [col for col in FEATURE_COLS if col in group.columns]
        group[available_cols] = group[available_cols].replace([np.inf, -np.inf], np.nan)
        group[available_cols] = group[available_cols].ffill().bfill().fillna(0)

        train, val, test = train_val_test_split_by_time(group)
        if min(len(train), len(val), len(test)) <= WINDOW:
            print(f"Skipping {commodity}: not enough rows for window={WINDOW}")
            continue

        scaler = MinMaxScaler()
        X_train = scaler.fit_transform(train[available_cols])
        X_val = scaler.transform(val[available_cols])
        X_test = scaler.transform(test[available_cols])

        X_train_seq, y_train_seq, _ = make_sequences(
            X_train, train["target_price"], train["price_date"]
        )
        X_val_seq, y_val_seq, _ = make_sequences(X_val, val["target_price"], val["price_date"])
        X_test_seq, y_test_seq, test_dates = make_sequences(
            X_test, test["target_price"], test["price_date"]
        )

        model = build_model(len(available_cols))
        model_path = MODEL_DIR / f"lstm_{commodity}.h5"
        callbacks = [
            EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True),
            ModelCheckpoint(str(model_path), monitor="val_loss", save_best_only=True),
        ]
        model.fit(
            X_train_seq,
            y_train_seq,
            validation_data=(X_val_seq, y_val_seq),
            epochs=100,
            batch_size=32,
            callbacks=callbacks,
            shuffle=False,
            verbose=1,
        )

        val_pred = model.predict(X_val_seq).ravel()
        residual_std = float(np.std(y_val_seq - val_pred))
        test_pred = model.predict(X_test_seq).ravel()
        lower = test_pred - 1.96 * residual_std
        upper = test_pred + 1.96 * residual_std
        importance = shap_importance(model, X_train_seq, X_test_seq, available_cols)

        metrics.append(
            metric_row(
                "LSTM",
                commodity,
                y_test_seq,
                test_pred,
                extra=json.dumps({"top_features": list(importance)[:5]}),
            )
        )

        for date, pred, lo, hi in zip(test_dates, test_pred, lower, upper):
            forecast_rows.append(
                {
                    "date": pd.to_datetime(date).date(),
                    "commodity": commodity,
                    "predicted_price": float(pred),
                    "confidence_interval_lower": float(lo),
                    "confidence_interval_upper": float(hi),
                    "model_name": "LSTM",
                    "created_at": pd.Timestamp.utcnow(),
                }
            )

        print(f"Trained LSTM for {commodity}: rows={len(test_pred)}, model={model_path}")

    forecast_df = pd.DataFrame(forecast_rows)
    replace_forecast(con, "gold.forecast_lstm", forecast_df, "LSTM")
    replace_metrics(con, metrics, ["LSTM"])
    con.close()
    print("LSTM forecast complete")


if __name__ == "__main__":
    main()
