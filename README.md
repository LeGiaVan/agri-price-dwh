# 🌾 agri-price-dwh

> **Nhà kho dữ liệu — Phân tích & Dự báo Giá Nông sản Việt Nam**  
> Môn học: Nhà kho dữ liệu & Tích hợp | Nhóm 5 thành viên | 2025

[![Ingest Status](https://github.com/{ORG}/agri-price-dwh/actions/workflows/ingest.yml/badge.svg)](https://github.com/{ORG}/agri-price-dwh/actions)

---

## 📋 Tổng quan

Hệ thống thu thập, làm sạch, lưu trữ và dự báo giá **5 mặt hàng nông sản xuất khẩu chủ lực của Việt Nam**: lúa gạo, cà phê, hồ tiêu, điều, cao su.

Kiến trúc: **Medallion (Bronze → Silver → Gold)** trên MotherDuck + dbt + LSTM/ARIMA + Streamlit GenBI.

```
FAO API / World Bank API
        │
        ▼ (GitHub Actions, 0h hàng ngày)
  ┌─────────────┐
  │   BRONZE    │  Dữ liệu thô, nguyên bản
  └──────┬──────┘
         │ dbt
         ▼
  ┌─────────────┐
  │   SILVER    │  Đã làm sạch, chuẩn hóa
  └──────┬──────┘
         │ dbt
         ▼
  ┌─────────────┐
  │    GOLD     │  Star schema Kimball + ML features
  └──────┬──────┘
         │
    ┌────┴────┐
    ▼         ▼
  LSTM      Streamlit
  ARIMA     + Groq GenBI
```

---

## 🗂️ Cấu trúc thư mục

```
agri-price-dwh/
├── .github/workflows/
│   └── ingest.yml          # GitHub Actions tự động chạy 0h VN
├── ingest/
│   ├── fao_ingest.py       # Thu thập FAO / HuggingFace  [Thành viên 1]
│   ├── worldbank_ingest.py # Thu thập World Bank API     [Thành viên 1]
│   └── utils.py            # Logger, retry helper
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml        # Kết nối MotherDuck (KHÔNG commit)
│   └── models/
│       ├── bronze/         # sources.yml
│       ├── silver/         # Làm sạch dữ liệu            [Thành viên 2]
│       └── gold/           # Star schema + ML features   [Thành viên 2]
├── ml/
│   ├── 01_arima_baseline.ipynb                           [Thành viên 3]
│   ├── 02_lstm_forecast.ipynb                            [Thành viên 3]
│   └── models/             # .h5 weights sau khi train
├── dashboard/
│   ├── app.py              # Streamlit main app           [Thành viên 4]
│   ├── genbi_chat.py       # Groq chatbot integration     [Thành viên 4]
│   └── requirements.txt
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── logs/                   # Ingest logs (gitignored)
├── .env.example            # Template biến môi trường
├── .gitignore
├── requirements.txt        # Python dependencies
├── CONTRIBUTING.md         # Quy trình làm việc nhóm
└── README.md
```

---

## ⚡ Quickstart (5 phút)

### 1. Clone repo

```bash
git clone https://github.com/{ORG}/agri-price-dwh.git
cd agri-price-dwh
```

### 2. Tạo file `.env`

```bash
cp .env.example .env
```

Mở `.env` và điền token thật vào:

```env
MOTHERDUCK_TOKEN=md_token_xxxxxxxxxxxxx
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxx
```

> 📌 Xin token ở đâu?
> - **MotherDuck**: [app.motherduck.com](https://app.motherduck.com) → Settings → Access Tokens
> - **HuggingFace**: [hf.co/settings/tokens](https://huggingface.co/settings/tokens) → New token (Read)
> - **Groq**: [console.groq.com](https://console.groq.com) → API Keys → Create

### 3. Tạo virtual environment (khuyến nghị)

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 4. Khởi tạo database MotherDuck

```bash
python db_init.py
```

Kết quả mong đợi:
```
✅ Connected to MotherDuck
✅ Schema bronze created
✅ Schema silver created
✅ Schema gold created
```

### 5. Chạy bằng Docker (tuỳ chọn)

```bash
# Chạy ingest thủ công
docker-compose -f docker/docker-compose.yml run --rm ingest

# Chạy dbt transformations
docker-compose -f docker/docker-compose.yml run --rm dbt dbt run

# Chạy dashboard (truy cập http://localhost:8501)
docker-compose -f docker/docker-compose.yml up dashboard
```

---

## 🗄️ Mô hình dữ liệu (Star Schema)

```
                    ┌─────────────────┐
                    │  dim_commodity  │
                    │─────────────────│
                    │ commodity_id PK │
                    │ name_vi         │
                    │ name_en         │
                    │ category        │
                    └────────┬────────┘
                             │
┌───────────┐      ┌─────────▼──────────┐      ┌─────────────┐
│ dim_date  │      │  fact_price_daily  │      │ dim_region  │
│───────────│      │────────────────────│      │─────────────│
│ date_id PK├──────┤ price_id  PK       ├──────┤ region_id PK│
│ date      │      │ commodity_id  FK   │      │ country     │
│ year      │      │ date_id  FK        │      │ province    │
│ month     │      │ region_id  FK      │      │ market_name │
│ quarter   │      │ price_usd          │      └─────────────┘
│ is_harvest│      │ price_vnd          │
└───────────┘      │ price_change_pct   │
                   │ price_7d_avg       │
                   │ source             │
                   └────────────────────┘
```

---

## 🤖 AI/ML Pipeline

| Model | Thư viện | Mục tiêu | Metrics |
|---|---|---|---|
| ARIMA | pmdarima | Baseline dự báo 30 ngày | RMSE, MAPE |
| LSTM | TensorFlow/Keras | Dự báo nâng cao | RMSE, MAPE |
| SHAP | shap | Giải thích feature importance | — |

**Ngưỡng chấp nhận**: MAPE < 10% trên tập test.

---

## 📊 Dashboard

Truy cập sau khi deploy: `https://{app-name}.streamlit.app`

| Trang | Nội dung |
|---|---|
| Tổng quan | Metric cards, line chart giá theo thời gian |
| Phân tích | Heatmap mùa vụ, so sánh mặt hàng, tương quan |
| Dự báo | LSTM/ARIMA forecast + confidence interval |
| Trợ lý AI | Chat tiếng Việt với Groq Llama 3 (GenBI) |

---

## 👥 Phân công nhóm

| Thành viên | Vai trò | Nhánh làm việc |
|---|---|---|
| Nhóm trưởng | Infrastructure, Architecture | `main` |
| Thành viên 1 | Data Ingestion | `feature/ingest-pipeline` |
| Thành viên 2 | dbt Transformation | `feature/dbt-silver-gold` |
| Thành viên 3 | ML Engineering | `feature/ml-forecasting` |
| Thành viên 4 | Dashboard & GenBI | `feature/dashboard-genbi` |

---

## 🔧 Lệnh dbt thường dùng

```bash
cd dbt

# Kiểm tra kết nối
dbt debug

# Chạy toàn bộ
dbt run

# Chỉ chạy Silver
dbt run --select silver

# Chỉ chạy Gold
dbt run --select gold

# Chạy tests
dbt test

# Xem docs
dbt docs generate && dbt docs serve
```

---

## 🚀 GitHub Actions

Workflow `ingest.yml` tự động chạy lúc **0h00 VN** mỗi ngày.

Để trigger thủ công: GitHub repo → tab **Actions** → **Daily Ingest** → **Run workflow**.

---

## ❓ Hỏi đáp

Gặp vấn đề? Tạo **Issue** trên GitHub hoặc hỏi trong nhóm chat.  
Xem thêm: [CONTRIBUTING.md](./CONTRIBUTING.md) để biết quy trình làm việc.