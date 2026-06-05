# Handoff Docker cho phan ML

File nay danh cho thanh vien tiep theo lam ARIMA/LSTM. Muc tieu cua phan Docker la giup chay ML trong container bang token MotherDuck trong `.env`, khong phu thuoc Google Colab.

## Dieu kien dau vao

Can co file `.env` o root repo:

```env
MOTHERDUCK_TOKEN=...
MOTHERDUCK_DB=agri_dwh
```

Truoc khi train ML, can chay xong Bronze va dbt Silver/Gold:

```powershell
cd D:\UIUX\datawarehouse\docker

docker compose run --rm db_init
docker compose run --rm fao_bronze_seed
docker compose run --rm ingest python ingest/worldbank_ingest.py

docker compose run --rm dbt dbt seed --profiles-dir .
docker compose run --rm dbt dbt build --profiles-dir . --select silver gold
```

Bang dau vao cho ML:

- `gold.gold_ml_features`

## Docker services da chuan bi

Compose da co 2 service rieng cho ML:

- `ml_arima`: chay `python ml/arima_baseline.py`
- `ml_lstm`: chay `python ml/lstm_forecast.py`

Build image ML:

```powershell
docker compose build ml_arima ml_lstm
```

Chay ARIMA baseline:

```powershell
docker compose run --rm ml_arima
```

Chay LSTM + SHAP:

```powershell
docker compose run --rm ml_lstm
```

## Output ky vong

Sau khi chay thanh cong, script se ghi ket qua ve MotherDuck:

- `gold.forecast_arima`
- `gold.forecast_lstm`
- `gold.model_metrics`

Va ghi file trong repo:

- `ml/model_evaluation.md`
- `ml/models/lstm_rice.h5`
- `ml/models/lstm_coffee.h5`
- `ml/models/lstm_pepper.h5`

## Luu y cho thanh vien ML

- Neu can notebook dung de nop bai, co the copy logic tu:
  - `ml/arima_baseline.py`
  - `ml/lstm_forecast.py`
- Docker da cai cac dependency ML trong `ml/requirements.txt`, gom `pmdarima`, `statsmodels`, `tensorflow`, `shap`.
- LSTM image build se nang va lau hon ARIMA vi TensorFlow/SHAP.
- File `.h5` dang bi ignore trong `.gitignore`; neu bat buoc commit model weights thi can sua `.gitignore` hoac dung Git LFS.
