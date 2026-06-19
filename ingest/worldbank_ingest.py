import pandas as pd
import duckdb
import os
import logging
from dotenv import load_dotenv

try:
    from ingest.utils import motherduck_connection
except ImportError:
    from utils import motherduck_connection

load_dotenv()
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("logs/ingest_error.log"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

WB_EXCEL_URL = "https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx"


def ingest_worldbank():
    try:
        log.info("--- 1. Đang tải và phân tích cấu hình file Excel ---")
        # Đọc file với skiprows=4 (thường là dòng bắt đầu có tên mặt hàng)
        df = pd.read_excel(WB_EXCEL_URL, sheet_name='Monthly Prices', skiprows=4)

        # Làm sạch tên cột (xóa khoảng trắng thừa)
        df.columns = [str(c).strip() for c in df.columns]

        # 2. Tìm cột 'Date' (thường là cột đầu tiên)
        date_col = df.columns[0]

        # 3. Tìm các cột dựa trên từ khóa (để tránh lỗi sai tên tuyệt đối)
        def find_col(keyword):
            for col in df.columns:
                if keyword.lower() in col.lower():
                    return col
            return None

        mapping = {
            find_col("Coffee, Arabica"): "coffee",
            find_col("Rice, Thai 5%"): "rice",
            find_col("Cocoa"): "cocoa",
            find_col("Cotton, A Index"): "cotton"
        }

        # Lọc bỏ các cột không tìm thấy
        selected_cols = {k: v for k, v in mapping.items() if k is not None}

        log.info(f"Đã tìm thấy các cột: {list(selected_cols.keys())}")

        # 4. Lọc và định dạng lại dữ liệu
        df_filtered = df[[date_col] + list(selected_cols.keys())].copy()
        df_filtered = df_filtered.rename(columns={date_col: 'price_date'})

        # Chuyển từ bảng ngang sang bảng dọc
        df_melted = df_filtered.melt(id_vars=['price_date'], var_name='original_name', value_name='price_usd')

        # Đổi tên mặt hàng về tên chuẩn
        df_melted['commodity'] = df_melted['original_name'].map(selected_cols)
        df_melted['source'] = 'world_bank_pink_sheet'
        df_melted['ingested_at'] = pd.Timestamp.utcnow()

        # Loại bỏ các dòng không có giá trị (NaN)
        df_melted = df_melted.dropna(subset=['price_usd'])
        df_melted['price_date'] = df_melted['price_date'].astype(str)

        log.info(f"--- 3. Đang nạp {len(df_melted)} dòng vào MotherDuck ---")
        con = motherduck_connection()

        con.execute("CREATE TABLE IF NOT EXISTS bronze.wb_prices_raw AS SELECT * FROM df_melted WHERE 1=0")
        con.execute("ALTER TABLE bronze.wb_prices_raw ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMP")
        con.register("incoming_wb_prices", df_melted)
        con.execute("""
        DELETE FROM bronze.wb_prices_raw
        WHERE (price_date, commodity, source) IN (
            SELECT price_date, commodity, source FROM incoming_wb_prices
        )
        """)
        con.execute("INSERT INTO bronze.wb_prices_raw SELECT * FROM incoming_wb_prices")
        con.unregister("incoming_wb_prices")

        count = con.execute("SELECT COUNT(*) FROM bronze.wb_prices_raw").fetchone()[0]
        log.info(f"THÀNH CÔNG: World Bank nạp được {count} dòng.")
        con.close()

    except Exception as e:
        log.error(f"Lỗi: {e}")


if __name__ == "__main__":
    ingest_worldbank()
