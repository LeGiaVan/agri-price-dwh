# README: Quy trình train ARIMA baseline và LSTM cho chuỗi thời gian giá nông sản

Tài liệu này hướng dẫn thứ tự làm notebook `01_arima_baseline.ipynb` và `02_lstm_forecast.ipynb` sau khi đã có dữ liệu từ Silver/Gold trong MotherDuck.

Mục tiêu chính:

- Train model dự báo giá cho từng mặt hàng: `rice`, `coffee`, `pepper`.
- Tránh data leakage, bias do chia dữ liệu sai thời gian, và ảnh hưởng quá mạnh từ outlier.
- Lưu kết quả dự báo về MotherDuck để dashboard/BI dùng được.

## 1. Kiểm tra điều kiện đầu vào

Trước khi train, cần đảm bảo dbt đã build xong các bảng:

- `silver.silver_fao_prices`
- `silver.silver_wb_prices`
- `gold.fact_price_daily`
- `gold.gold_ml_features`

Chạy dbt:

```powershell
cd dbt
dbt build --profiles-dir . --select silver gold
```

Kết nối MotherDuck trong notebook:

```python
import os
import duckdb
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("MOTHERDUCK_TOKEN")
con = duckdb.connect(f"md:agri_dwh?motherduck_token={token}")

df = con.execute("""
    select *
    from gold.gold_ml_features
    where commodity in ('rice', 'coffee', 'pepper')
    order by commodity, price_date
""").fetchdf()
```

## 2. Hiểu đúng bài toán dự báo

Không nên dùng dữ liệu của ngày `t` để dự báo chính giá ngày `t`, vì nhiều feature trong `gold.gold_ml_features` có thể đã chứa thông tin của ngày đó, ví dụ:

- `price_usd_per_kg`
- `price_change_pct`
- `price_7d_avg`
- `price_30d_avg`
- `price_90d_avg`
- `price_30d_volatility`

Cách an toàn hơn:

- Dùng feature tại ngày `t` để dự báo giá ngày kế tiếp `t+1`.
- Tạo target bằng `shift(-1)` theo từng commodity.

```python
df["price_date"] = pd.to_datetime(df["price_date"])
df = df.sort_values(["commodity", "price_date"])

df["target_price"] = (
    df.groupby("commodity")["price_usd_per_kg"]
      .shift(-1)
)

df = df.dropna(subset=["target_price"])
```

Nếu muốn dự báo cùng ngày `t`, cần sửa SQL rolling feature trong dbt để chỉ dùng dữ liệu quá khứ, ví dụ `rows between 30 preceding and 1 preceding` thay vì `current row`.

## 3. Kiểm tra chất lượng dữ liệu

Làm các bước này trước khi train:

```python
summary = (
    df.groupby("commodity")
      .agg(
          min_date=("price_date", "min"),
          max_date=("price_date", "max"),
          rows=("price_date", "count"),
          missing_price=("price_usd_per_kg", lambda s: s.isna().sum()),
          avg_price=("price_usd_per_kg", "mean"),
      )
)

display(summary)
```

Cần kiểm tra:

- Mỗi commodity có đủ số dòng không.
- Tần suất dữ liệu là daily, monthly hay bị đứt quãng.
- Có giá bằng 0, âm, null, hoặc spike quá bất thường không.
- `WORLD_BANK` thường là dữ liệu global/monthly, còn `FAO` có thể khác vùng/tần suất. Khi gộp nguồn, cần cẩn thận bias theo source.

## 4. Chia train/validation/test theo thời gian

Không dùng `train_test_split(..., shuffle=True)`.

Khuyến nghị:

- Train: trước `2023-01-01`
- Validation: `2023-01-01` đến `2023-12-31`
- Test cuối: `2024-01-01` đến `2024-12-31`

```python
train_df = df[df["price_date"] < "2023-01-01"]
val_df = df[(df["price_date"] >= "2023-01-01") & (df["price_date"] < "2024-01-01")]
test_df = df[(df["price_date"] >= "2024-01-01") & (df["price_date"] < "2025-01-01")]
```

Lý do:

- Train là dữ liệu quá khứ.
- Validation dùng để chỉnh tham số, early stopping, chọn model.
- Test 2024 chỉ dùng một lần cuối cùng để báo cáo kết quả thật.

## 5. Xử lý outlier đúng cách

Outlier trong chuỗi giá nông sản có hai loại:

- Lỗi dữ liệu: sai đơn vị, duplicate, parse nhầm.
- Cú sốc thật: biến động thị trường, mùa vụ, chính sách, cung cầu.

Không nên xóa toàn bộ spike. Cách hợp lý hơn:

1. Detect outlier theo từng commodity.
2. Tạo cột `is_outlier`.
3. Winsorize/cap nhẹ giá trị quá cực đoan.
4. Fit ngưỡng outlier chỉ trên train, sau đó áp dụng cho validation/test.

Ví dụ đơn giản:

```python
def cap_by_train_quantile(train_part, other_part, col):
    lower = train_part[col].quantile(0.01)
    upper = train_part[col].quantile(0.99)
    capped = other_part[col].clip(lower, upper)
    return capped, lower, upper

parts = []

for commodity, group in df.groupby("commodity"):
    group = group.sort_values("price_date").copy()
    train_mask = group["price_date"] < "2023-01-01"

    train_prices = group.loc[train_mask, "price_usd_per_kg"]
    lower = train_prices.quantile(0.01)
    upper = train_prices.quantile(0.99)

    group["is_outlier"] = (
        (group["price_usd_per_kg"] < lower) |
        (group["price_usd_per_kg"] > upper)
    ).astype(int)

    group["price_clean"] = group["price_usd_per_kg"].clip(lower, upper)
    parts.append(group)

df_clean = pd.concat(parts, ignore_index=True)
```

Quan trọng: không tính quantile bằng toàn bộ dữ liệu, vì như vậy validation/test đã ảnh hưởng đến bước xử lý train.

## 6. ARIMA baseline

ARIMA nên là baseline đơn giản, train riêng từng commodity.

Input chính:

- `price_clean` hoặc `price_usd_per_kg`
- Không cần nhiều feature ngoài chuỗi giá.

Các bước:

1. Lấy chuỗi giá của từng commodity.
2. Kiểm tra stationarity bằng ADF test.
3. Nếu không dừng thì differencing.
4. Dùng `auto_arima` chọn `(p,d,q)`.
5. Forecast trên validation/test.
6. Tính RMSE, MAE, MAPE.

Ví dụ khung code:

```python
from pmdarima import auto_arima
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np

def mape(y_true, y_pred):
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    mask = y_true != 0
    return np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100

results = []
forecast_rows = []

for commodity in ["rice", "coffee", "pepper"]:
    data = df_clean[df_clean["commodity"] == commodity].sort_values("price_date")

    train = data[data["price_date"] < "2023-01-01"]
    test = data[(data["price_date"] >= "2023-01-01") & (data["price_date"] < "2025-01-01")]

    y_train = train["price_clean"]
    y_test = test["target_price"]

    model = auto_arima(
        y_train,
        seasonal=False,
        stepwise=True,
        suppress_warnings=True,
        error_action="ignore"
    )

    pred = model.predict(n_periods=len(test))

    rmse = mean_squared_error(y_test, pred, squared=False)
    mae = mean_absolute_error(y_test, pred)
    score_mape = mape(y_test, pred)

    results.append({
        "model": "ARIMA",
        "commodity": commodity,
        "rmse": rmse,
        "mae": mae,
        "mape": score_mape,
        "order": str(model.order)
    })

    forecast_rows.extend([
        {
            "date": date,
            "commodity": commodity,
            "predicted_price": float(value),
            "model_name": "ARIMA"
        }
        for date, value in zip(test["price_date"], pred)
    ])
```

Nên so thêm với naive baseline:

```python
test["naive_pred"] = test["price_lag_1"]
```

Nếu ARIMA hoặc LSTM không tốt hơn naive baseline thì model chưa có giá trị thực tế.

## 7. LSTM nâng cao

LSTM dùng nhiều feature hơn ARIMA, nhưng vẫn phải giữ nguyên quy tắc thời gian.

Feature gợi ý:

```python
feature_cols = [
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
```

Fit scaler chỉ trên train:

```python
from sklearn.preprocessing import MinMaxScaler

scaler = MinMaxScaler()

X_train_raw = train_df[feature_cols]
X_val_raw = val_df[feature_cols]
X_test_raw = test_df[feature_cols]

X_train_scaled = scaler.fit_transform(X_train_raw)
X_val_scaled = scaler.transform(X_val_raw)
X_test_scaled = scaler.transform(X_test_raw)
```

Tạo sequence window 30:

```python
def make_sequences(X, y, dates, window=30):
    X_seq, y_seq, date_seq = [], [], []

    for i in range(window, len(X)):
        X_seq.append(X[i - window:i])
        y_seq.append(y.iloc[i])
        date_seq.append(dates.iloc[i])

    return np.array(X_seq), np.array(y_seq), np.array(date_seq)
```

Architecture:

```python
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dropout, Dense
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint

model = Sequential([
    LSTM(64, return_sequences=True, input_shape=(30, len(feature_cols))),
    Dropout(0.2),
    LSTM(32),
    Dense(1)
])

model.compile(optimizer="adam", loss="mse")
```

Train:

```python
callbacks = [
    EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True),
    ModelCheckpoint(
        filepath=f"ml/models/lstm_{commodity}.h5",
        monitor="val_loss",
        save_best_only=True
    )
]

history = model.fit(
    X_train_seq,
    y_train_seq,
    validation_data=(X_val_seq, y_val_seq),
    epochs=100,
    batch_size=32,
    callbacks=callbacks,
    shuffle=False
)
```

Không bật `shuffle=True` khi train time series.

## 8. Confidence interval cho LSTM

LSTM không tự có confidence interval như một số model thống kê. Cách đơn giản cho bài này:

1. Tính residual trên validation.
2. Lấy độ lệch chuẩn residual.
3. Dự báo test cộng/trừ `1.96 * std`.

```python
val_pred = model.predict(X_val_seq).ravel()
residual_std = np.std(y_val_seq - val_pred)

test_pred = model.predict(X_test_seq).ravel()

lower = test_pred - 1.96 * residual_std
upper = test_pred + 1.96 * residual_std
```

Cách này là baseline interval, không phải uncertainty hoàn hảo, nhưng đủ rõ ràng cho dashboard/demo.

## 9. SHAP cho LSTM

Mục tiêu SHAP:

- Giải thích feature nào ảnh hưởng đến dự báo.
- Ví dụ: giá hôm qua, giá tuần trước, mùa vụ, volatility.

Với LSTM, có thể dùng `shap.DeepExplainer`, nhưng nên lấy sample nhỏ để chạy nhanh:

```python
import shap

background = X_train_seq[:100]
explain_sample = X_test_seq[:50]

explainer = shap.DeepExplainer(model, background)
shap_values = explainer.shap_values(explain_sample)
```

Khi báo cáo, nên tổng hợp importance theo feature, không chỉ theo từng timestep.

## 10. Đánh giá model

Tạo bảng so sánh rõ ràng:

| model | commodity | rmse | mae | mape |
|---|---|---:|---:|---:|
| Naive | rice | ... | ... | ... |
| ARIMA | rice | ... | ... | ... |
| LSTM | rice | ... | ... | ... |

Giải thích metric:

- RMSE: phạt mạnh lỗi lớn, nhạy với outlier.
- MAE: dễ hiểu, lỗi trung bình tuyệt đối.
- MAPE: lỗi phần trăm, dễ trình bày, nhưng không ổn nếu giá gần 0.

Ngưỡng tham khảo:

- MAPE dưới 10%: tốt cho demo.
- LSTM nên tốt hơn Naive và ARIMA thì mới gọi là nâng cao có giá trị.

## 11. Lưu kết quả về MotherDuck

ARIMA:

```sql
create schema if not exists gold;

create table if not exists gold.forecast_arima (
    date date,
    commodity varchar,
    predicted_price double,
    model_name varchar,
    created_at timestamp
);
```

LSTM:

```sql
create table if not exists gold.forecast_lstm (
    date date,
    commodity varchar,
    predicted_price double,
    confidence_interval_lower double,
    confidence_interval_upper double,
    model_name varchar,
    created_at timestamp
);
```

Insert bằng DataFrame:

```python
forecast_df["created_at"] = pd.Timestamp.utcnow()

con.register("forecast_df", forecast_df)
con.execute("""
    insert into gold.forecast_lstm
    select *
    from forecast_df
""")
```

## 12. File cần nộp/commit

Các file nên có:

- `ml/01_arima_baseline.ipynb`
- `ml/02_lstm_forecast.ipynb`
- `ml/model_evaluation.md`
- `ml/models/lstm_rice.h5`
- `ml/models/lstm_coffee.h5`
- `ml/models/lstm_pepper.h5`

Lưu ý: repo hiện đang ignore `ml/models/*.h5`. Nếu yêu cầu bắt buộc commit model `.h5`, cần sửa `.gitignore` hoặc dùng Git LFS.

## 13. Checklist chống lỗi thường gặp

- Không random split dữ liệu chuỗi thời gian.
- Không fit scaler trên toàn bộ dữ liệu.
- Không detect outlier bằng cả validation/test.
- Không dùng feature ngày `t` để dự báo target ngày `t` nếu feature có chứa giá ngày `t`.
- Không báo mỗi average metric, phải báo riêng từng commodity.
- Không chỉ so ARIMA với LSTM, cần thêm Naive baseline.
- Không dùng test set để chọn hyperparameter.
- Không train LSTM nếu dữ liệu thực tế là monthly nhưng lại giả định daily window 30 ngày.

## 14. Thứ tự làm đề xuất

1. Build dbt Silver/Gold.
2. Load `gold.gold_ml_features`.
3. Kiểm tra số dòng, date range, missing, tần suất dữ liệu.
4. Tạo `target_price = shift(-1)`.
5. Split train/validation/test theo ngày.
6. Detect/cap outlier bằng ngưỡng học từ train.
7. Train Naive baseline.
8. Train ARIMA baseline.
9. Train LSTM.
10. Tính RMSE, MAE, MAPE.
11. So sánh Naive vs ARIMA vs LSTM.
12. Chạy SHAP cho LSTM.
13. Lưu forecast vào `gold.forecast_arima` và `gold.forecast_lstm`.
14. Viết `model_evaluation.md`.
15. Commit notebook, evaluation report, và model weights nếu được yêu cầu.

