import yfinance as yf
import duckdb, os, pandas as pd, logging
import requests  # Thêm thư viện này
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Cấu hình giả lập trình duyệt để tránh bị Yahoo chặn
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
})

TICKERS = {
    "KC=F": "coffee",
    "ZR=F": "rice",
    "PA=F": "palm_oil",
    "CC=F": "cocoa",
    "CT=F": "cotton"
}


def ingest():
    frames = []
    for ticker, name in TICKERS.items():
        try:
            print(f"--- Đang lấy giá: {name} ({ticker}) ---")
            # Thêm tham số session=session vào đây
            df = yf.download(ticker, period="2y", interval="1d", progress=False, session=session)

            if df.empty or len(df) < 1:
                print(f"⚠️ Cảnh báo: Ticker {ticker} không có dữ liệu.")
                continue

            df = df[["Close"]].reset_index()
            df.columns = ["price_date", "price_usd"]
            df["commodity"] = name
            df["source"] = "yahoo_finance"
            frames.append(df)
            log.info(f"{name}: {len(df)} dòng")
        except Exception as e:
            log.error(f"Lỗi {name}: {e}")

    if not frames:
        print("Không lấy được dữ liệu nào. Có thể Yahoo đang chặn IP của bạn.")
        return

    combined = pd.concat(frames, ignore_index=True)
    combined["price_date"] = combined["price_date"].astype(str)

    con = duckdb.connect("md:agri_dwh")
    con.execute(
        "CREATE TABLE IF NOT EXISTS bronze.yf_prices_raw (price_date VARCHAR, price_usd DOUBLE, commodity VARCHAR, source VARCHAR)")

    con.execute("""
    INSERT INTO bronze.yf_prices_raw
    SELECT * FROM combined
    WHERE (price_date, commodity) NOT IN (SELECT price_date, commodity FROM bronze.yf_prices_raw)
    """)

    res = con.execute("SELECT COUNT(*) FROM bronze.yf_prices_raw").fetchone()[0]
    print(f"THÀNH CÔNG! Tổng cộng có {res} dòng trong Database.")
    con.close()


if __name__ == "__main__":
    ingest()