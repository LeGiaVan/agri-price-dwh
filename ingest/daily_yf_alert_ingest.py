import os
import sys
import logging
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
from groq import Groq

# Thêm parent directory vào sys.path để import utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from ingest.utils import get_logger, motherduck_connection
except ImportError:
    from utils import get_logger, motherduck_connection

LOG = get_logger("ingest.daily_yf_alert_ingest")

THRESHOLDS = {
    "coffee": 5.0,
    "rice": 3.0,
    "cocoa": 5.0,
    "cotton": 4.0
}

# THRESHOLDS = {
#     "coffee": 0.001,
#     "rice": 0.001,
#     "cocoa": 0.001,
#     "cotton": 0.001
# }


YAHOO_CONTRACTS = {
    "KC=F": "coffee",
    "ZR=F": "rice",
    "CC=F": "cocoa",
    "CT=F": "cotton"
}

LB_TO_KG = 0.45359237
CWT_TO_KG = 45.359237
CONVERSIONS = {
    "coffee": lambda p: (p / 100.0) / LB_TO_KG,
    "cocoa": lambda p: p / 1000.0,
    "cotton": lambda p: (p / 100.0) / LB_TO_KG,
    "rice": lambda p: (p / CWT_TO_KG) * 2.2, # ZR=F is in USD/cwt (Rough Rice), multiply by 2.2 to approximate Thai 5% Milled Rice
}

def setup_alert_table(con):
    con.execute("""
        CREATE SCHEMA IF NOT EXISTS bronze;
        CREATE TABLE IF NOT EXISTS bronze.price_alerts (
            alert_id VARCHAR,
            alert_date DATE,
            commodity VARCHAR,
            old_price DOUBLE,
            new_price DOUBLE,
            pct_change DOUBLE,
            threshold DOUBLE,
            ai_comment TEXT,
            created_at TIMESTAMP
        )
    """)
    # Đảm bảo bảng yf_prices_raw tồn tại (schema giống daily_cron cũ)
    con.execute("""
        CREATE TABLE IF NOT EXISTS bronze.yf_prices_raw (
            price_date DATE,
            price_usd DOUBLE,
            price_usd_per_kg DOUBLE,
            commodity VARCHAR,
            source VARCHAR,
            ticker VARCHAR,
            raw_unit VARCHAR,
            currency VARCHAR,
            region VARCHAR,
            country VARCHAR,
            ingested_at TIMESTAMP
        )
    """)
    for column, data_type in {
        "price_usd_per_kg": "DOUBLE",
        "ticker": "VARCHAR",
        "raw_unit": "VARCHAR",
        "currency": "VARCHAR",
        "region": "VARCHAR",
        "country": "VARCHAR",
        "ingested_at": "TIMESTAMP",
    }.items():
        try:
            con.execute(f"ALTER TABLE bronze.yf_prices_raw ADD COLUMN {column} {data_type}")
        except Exception:
            pass

def get_last_price(con, commodity):
    try:
        res = con.execute(f"SELECT price_usd_per_kg FROM bronze.yf_prices_raw WHERE commodity = '{commodity}' AND CAST(price_date AS DATE) < CURRENT_DATE ORDER BY price_date DESC LIMIT 1").fetchone()
        if res:
            return res[0]
    except Exception as e:
        LOG.error(f"Lỗi truy vấn giá cũ cho {commodity}: {e}")
    return None

def fetch_today_price(ticker):
    # Lấy dữ liệu 1 ngày gần nhất
    df = yf.download(ticker, period="1d", interval="1d", progress=False)
    if not df.empty:
        # Xử lý trường hợp yfinance trả về MultiIndex hoặc Index đơn
        if isinstance(df.columns, pd.MultiIndex):
            if ("Close", ticker) in df.columns:
                return float(df["Close"][ticker].iloc[0])
            else:
                return float(df["Close"].iloc[0, 0])
        else:
            return float(df["Close"].iloc[0])
    return None

def call_groq_api(commodity, old_price, new_price, pct_change):
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        LOG.warning("Không tìm thấy GROQ_API_KEY trong .env. Bỏ qua nhận xét AI.")
        return "Không có phân tích AI (thiếu API key)."
        
    try:
        client = Groq(api_key=groq_api_key)
        direction = "tăng" if pct_change > 0 else "giảm"
        prompt = f"Giá của mặt hàng nông sản {commodity} vừa {direction} {abs(pct_change):.2f}% (từ {old_price:.4f} USD/kg lên {new_price:.4f} USD/kg). Hãy viết 1 đoạn phân tích ngắn gọn (tiếng Việt, 2-3 câu) giải thích ngắn gọn nguyên nhân có thể gây ra biến động này theo tình hình cung cầu thị trường nông sản chung. Trả lời trực tiếp vào vấn đề, không cần chào hỏi."
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama-3.1-8b-instant",
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        LOG.error(f"Lỗi gọi Groq API: {e}")
        return f"Không thể tạo cảnh báo AI do lỗi API."

def send_email_alert(commodity, old_price, new_price, pct_change, ai_comment):
    sender = os.getenv("EMAIL_SENDER")
    pwd = os.getenv("EMAIL_PASSWORD")
    receiver = os.getenv("EMAIL_RECEIVER")
    
    if not (sender and pwd and receiver):
        LOG.warning("Thiếu cấu hình Email (EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER). Bỏ qua gửi email.")
        return
        
    try:
        msg = EmailMessage()
        direction = "TĂNG" if pct_change > 0 else "GIẢM"
        msg['Subject'] = f"[CẢNH BÁO GIÁ] {commodity.upper()} {direction} MẠNH ({abs(pct_change):.2f}%)"
        msg['From'] = sender
        msg['To'] = receiver
        
        body = f"Cảnh báo biến động giá thị trường:\n\n"
        body += f"- Mặt hàng: {commodity}\n"
        body += f"- Giá cũ (phiên trước): {old_price:.4f} USD/kg\n"
        body += f"- Giá mới (hôm nay): {new_price:.4f} USD/kg\n"
        body += f"- Mức {direction.lower()}: {abs(pct_change):.2f}%\n\n"
        body += f"Phân tích từ AI:\n{ai_comment}\n\n"
        body += "Hệ thống DWH Agri-Price."
        
        msg.set_content(body)
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender, pwd)
            smtp.send_message(msg)
            
        LOG.info(f"Đã gửi email cảnh báo thành công cho {commodity}.")
    except Exception as e:
        LOG.error(f"Lỗi khi gửi email: {e}")

def ingest_and_alert():
    con = motherduck_connection()
    setup_alert_table(con)
    
    # yfinance cho 1d thường lấy giá chốt phiên gần nhất
    today_date = datetime.now().date()
    
    for ticker, commodity in YAHOO_CONTRACTS.items():
        try:
            LOG.info(f"--- Bắt đầu xử lý {commodity} ({ticker}) ---")
            
            raw_price = fetch_today_price(ticker)
            if raw_price is None or pd.isna(raw_price):
                LOG.warning(f"Không lấy được giá mới cho {ticker}. Bỏ qua.")
                continue
                
            new_price_kg = CONVERSIONS[commodity](raw_price)
            old_price_kg = get_last_price(con, commodity)
            
            if old_price_kg is not None and old_price_kg > 0:
                pct_change = ((new_price_kg - old_price_kg) / old_price_kg) * 100.0
                threshold = THRESHOLDS.get(commodity, 5.0)
                
                if abs(pct_change) >= threshold:
                    LOG.info(f"!!! CẢNH BÁO: {commodity} biến động {pct_change:.2f}% (Ngưỡng: {threshold}%) !!!")
                    # Gọi AI & Email (không throw lỗi để vẫn lưu DB được)
                    ai_comment = call_groq_api(commodity, old_price_kg, new_price_kg, pct_change)
                    send_email_alert(commodity, old_price_kg, new_price_kg, pct_change, ai_comment)
                    
                    # Lưu log cảnh báo vào database
                    alert_id = f"ALT_{commodity}_{today_date.strftime('%Y%m%d')}_{abs(pct_change):.0f}"
                    con.execute(f"""
                        INSERT INTO bronze.price_alerts 
                        (alert_id, alert_date, commodity, old_price, new_price, pct_change, threshold, ai_comment, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (alert_id, today_date, commodity, old_price_kg, new_price_kg, pct_change, threshold, ai_comment, datetime.now()))
                    LOG.info(f"Đã ghi log Alert vào Database cho {commodity}.")
            else:
                LOG.info(f"Không có giá cũ trong database cho {commodity} để so sánh.")
                
            # Lưu giá vào database (xóa nếu bị trùng lặp ngày hôm nay)
            con.execute(f"DELETE FROM bronze.yf_prices_raw WHERE price_date = '{today_date}' AND commodity = '{commodity}'")
            con.execute(f"""
                INSERT INTO bronze.yf_prices_raw 
                (price_date, price_usd, price_usd_per_kg, commodity, source, ticker, raw_unit, currency, region, country, ingested_at)
                VALUES (?, ?, ?, ?, 'yahoo_finance', ?, 'unit_contract', 'USD', 'US futures market', 'United States', ?)
            """, (today_date, raw_price, new_price_kg, commodity, ticker, datetime.now()))
            
            LOG.info(f"Đã lưu giá mới {new_price_kg:.4f} USD/kg cho {commodity} vào Database.")
            
        except Exception as e:
            LOG.error(f"Lỗi không mong muốn khi xử lý {commodity}: {e}")
            
    con.close()

if __name__ == "__main__":
    ingest_and_alert()
