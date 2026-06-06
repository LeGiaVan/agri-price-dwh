# Ghi chu phan Ingest va dbt Silver/Gold

Tai lieu nay tom tat phan da lam de nguoi nhan viec sau co the tiep tuc nhanh.

## Muc tieu

Pipeline dang di theo kien truc Medallion:

- Bronze: du lieu tho nap vao MotherDuck.
- Silver: lam sach, chuan hoa kieu du lieu, dedup.
- Gold: star schema Kimball va bang feature cho ML.

Phan da xu ly gom ingest FAO/World Bank vao Bronze va kiem tra dbt Silver/Gold.

## Cac file chinh

- `ingest/fao_ingest.py`: load dataset FAO tu HuggingFace bang thu vien `datasets`, filter 5 mat hang `rice`, `coffee`, `pepper`, `cashew`, `rubber`, roi insert vao `bronze.fao_prices_raw`.
- `ingest/worldbank_ingest.py`: goi World Bank Indicators API, neu API khong tra du lieu hop le thi fallback sang World Bank Pink Sheet monthly workbook, parse gia thang va insert vao `bronze.wb_prices_raw`.
- `ingest/utils.py`: logger, retry helper, ket noi MotherDuck, helper insert dataframe.
- `fao_bronze_seed.py`: tao du lieu bronze FAO mau/de phong khi dataset HuggingFace khong truy cap duoc, phuc vu test Silver/Gold.
- `.github/workflows/ingest.yml`: GitHub Actions chay ingest hang ngay luc `0 17 * * *` UTC, co `workflow_dispatch`.
- `docker/docker-compose.yml`: co service `fao_bronze_seed` de nguoi sau chay seed FAO bang Docker.

## Bien moi truong can co

Tao file `.env` o root repo theo `.env.example`:

```env
MOTHERDUCK_TOKEN=...
HF_TOKEN=...
MOTHERDUCK_DB=agri_dwh
```

`MOTHERDUCK_TOKEN` bat buoc de ghi/doc MotherDuck. `HF_TOKEN` dung cho HuggingFace neu dataset FAO co quyen truy cap.

## Tinh trang nguon du lieu

Dataset HuggingFace `mrm8488/fao-agricultural-market` hien co luc bi loi:

```text
DatasetNotFoundError: Dataset 'mrm8488/fao-agricultural-market' doesn't exist on the Hub or cannot be accessed.
```

Vi vay da them `fao_bronze_seed.py` lam fallback de tao bang `bronze.fao_prices_raw` va test duoc dbt Silver/Gold. Neu sau nay tim duoc dataset FAO thay the, chi can sua `ingest/fao_ingest.py` hoac bien `DATASET_NAME`.

World Bank Indicators API co the khong tra row cho mot so ma commodity indicator, nen `ingest/worldbank_ingest.py` fallback sang Pink Sheet monthly workbook cua World Bank.

## Cach chay bang Docker

Dung Docker theo huong cu cua nhom:

```powershell
cd D:\UIUX\datawarehouse\docker
```

Tao bang FAO bronze fallback:

```powershell
docker compose run --rm fao_bronze_seed
```

Chay World Bank ingest:

```powershell
docker compose run --rm ingest python ingest/worldbank_ingest.py
```

Seed bang mapping:

```powershell
docker compose run --rm dbt dbt seed --profiles-dir . --select commodity_mapping
```

Build va test Silver/Gold:

```powershell
docker compose run --rm dbt dbt build --profiles-dir . --select silver gold
```

Ket qua gan nhat da pass:

```text
PASS=54 WARN=0 ERROR=0 SKIP=0 TOTAL=54
```

## Cac bang chinh sau khi chay

Bronze:

- `bronze.fao_prices_raw`
- `bronze.wb_prices_raw`

Silver:

- `silver.silver_fao_prices`
- `silver.silver_wb_prices`

Gold:

- `gold.dim_commodity`
- `gold.dim_date`
- `gold.dim_region`
- `gold.fact_price_daily`
- `gold.gold_ml_features`

## Luu y khi commit

Nen commit cac file lien quan:

- `.github/workflows/ingest.yml`
- `ingest/fao_ingest.py`
- `ingest/worldbank_ingest.py`
- `ingest/utils.py`
- `fao_bronze_seed.py`
- `docker/docker-compose.yml`
- `README_INGEST_DBT_VI.md`

Khong nen commit:

- `.idea/*`
- `dbt/target/*`
- `logs/*`
- `.env`

## Viec nen lam tiep

- Xac nhan nguon FAO thay the neu dataset HuggingFace tiep tuc khong truy cap duoc.
- Trigger thu cong GitHub Actions `Daily Ingest` bang `workflow_dispatch`.
- Kiem tra log GitHub Actions va MotherDuck dashboard sau khi ingest chay tren CI.
