import streamlit as st
import duckdb, os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Giá Nông sản Việt Nam", page_icon="🌾", layout="wide")
st.title("🌾 Phân tích & Dự báo Giá Nông sản Việt Nam")
st.caption("agri-price-dwh | Data Lakehouse Project")

st.info("Dashboard đang được phát triển. Thành viên 4 sẽ hoàn thiện từ 05/06.", icon="🚧")

col1, col2, col3 = st.columns(3)
col1.metric("Trạng thái Ingest", "⏳ Chờ M1", "29/05")
col2.metric("Trạng thái dbt", "⏳ Chờ M2", "07/06")
col3.metric("Trạng thái ML", "⏳ Chờ M3", "11/06")
