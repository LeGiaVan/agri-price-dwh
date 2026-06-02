"""
fao_bronze_seed.py
------------------
Tạo bảng bronze.fao_prices_raw với dữ liệu giá nông sản lịch sử
dựa trên giá thực tế (FAO/World Bank historical prices).

Chạy: python fao_bronze_seed.py
Yêu cầu: MOTHERDUCK_TOKEN trong .env
"""

import os
import duckdb
import pandas as pd
from datetime import date
from dotenv import load_dotenv

load_dotenv()

# ── Giá tham khảo thực tế (USD/tấn, nguồn FAO/WB historical data) ──────────
# Mỗi entry: (commodity, year, month, price_usd_per_ton, region, country)
PRICE_DATA = []

# Rice (Việt Nam xuất khẩu, 5% broken) – nguồn: USDA/FAO
rice_prices = {
    2015: 370, 2016: 360, 2017: 390, 2018: 415, 2019: 380,
    2020: 490, 2021: 500, 2022: 450, 2023: 580, 2024: 560,
}

# Robusta Coffee (Việt Nam) – nguồn: ICO
coffee_prices = {
    2015: 1750, 2016: 1700, 2017: 2000, 2018: 1650, 2019: 1480,
    2020: 1450, 2021: 2000, 2022: 2300, 2023: 2800, 2024: 4200,
}

# Black Pepper (Việt Nam) – nguồn: IPC/FAO
pepper_prices = {
    2015: 8500, 2016: 7200, 2017: 5000, 2018: 3500, 2019: 2800,
    2020: 2600, 2021: 3500, 2022: 4000, 2023: 4200, 2024: 4800,
}

# Cashew (raw nut, Việt Nam) – nguồn: FAO
cashew_prices = {
    2015: 1500, 2016: 1800, 2017: 2200, 2018: 1700, 2019: 1400,
    2020: 1100, 2021: 1500, 2022: 1600, 2023: 1800, 2024: 2000,
}

# Rubber (RSS3, Việt Nam) – nguồn: ANRPC/FAO
rubber_prices = {
    2015: 1500, 2016: 1600, 2017: 2000, 2018: 1500, 2019: 1600,
    2020: 1700, 2021: 2000, 2022: 1800, 2023: 1500, 2024: 1700,
}

COMMODITY_CONFIG = [
    ("rice",    rice_prices,    "Vietnam", "Mekong Delta", "USD", "MT"),
    ("coffee",  coffee_prices,  "Vietnam", "Central Highlands", "USD", "MT"),
    ("pepper",  pepper_prices,  "Vietnam", "South East", "USD", "MT"),
    ("cashew",  cashew_prices,  "Vietnam", "South East", "USD", "MT"),
    ("rubber",  rubber_prices,  "Vietnam", "South East", "USD", "MT"),
]

import random
random.seed(42)

rows = []
for commodity, prices, country, region, currency, unit in COMMODITY_CONFIG:
    for year, base_price in prices.items():
        for month in range(1, 13):
            # Thêm seasonal variation ±8%
            seasonal = 1 + 0.08 * (month - 6.5) / 6.5 * (1 if month < 7 else -1)
            noise = random.uniform(0.96, 1.04)
            price = round(base_price * seasonal * noise, 2)

            rows.append({
                "commodity":    commodity,
                "date":         date(year, month, 1),
                "year":         year,
                "month":        month,
                "region":       region,
                "country":      country,
                "price":        price,
                "currency":     currency,
                "unit":         unit,
                "ingested_at":  pd.Timestamp.now(),
            })

df = pd.DataFrame(rows)
print(f"Generated {len(df)} rows")
print(df.groupby("commodity")["price"].describe().round(2))

# ── Kết nối MotherDuck và insert ────────────────────────────────────────────
token = os.getenv("MOTHERDUCK_TOKEN")
if not token:
    raise ValueError("MOTHERDUCK_TOKEN not set in .env")

con = duckdb.connect(f"md:agri_dwh?motherduck_token={token}")
con.execute("USE agri_dwh")

# Tạo bảng nếu chưa có
con.execute("""
    CREATE TABLE IF NOT EXISTS bronze.fao_prices_raw (
        commodity   VARCHAR,
        date        DATE,
        year        INTEGER,
        month       INTEGER,
        region      VARCHAR,
        country     VARCHAR,
        price       DECIMAL(18,6),
        currency    VARCHAR,
        unit        VARCHAR,
        ingested_at TIMESTAMP
    )
""")

# Xóa data cũ nếu có để tránh duplicate
con.execute("DELETE FROM bronze.fao_prices_raw")

# Insert
con.register("df_view", df)
con.execute("INSERT INTO bronze.fao_prices_raw SELECT * FROM df_view")

count = con.execute("SELECT COUNT(*) FROM bronze.fao_prices_raw").fetchone()[0]
print(f"\n✅ Inserted {count} rows into bronze.fao_prices_raw")

con.close()
print("Done.")