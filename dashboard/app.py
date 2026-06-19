import streamlit as st
import duckdb
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import os
import base64
from dotenv import load_dotenv

load_dotenv()

# ─── Icon loader ──────────────────────────────────────────────────────────────
ASSET_DIR = os.path.join(os.path.dirname(__file__), "asset")

def _load_logo() -> str:
    path = os.path.join(ASSET_DIR, "logo.png")
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return ""

LOGO_B64 = _load_logo()

# ─── Constants ────────────────────────────────────────────────────────────────
USD_TO_VND = 25_000

COMMODITY_VI = {
    'rice':   'Gạo',
    'coffee': 'Cà phê',
    'pepper': 'Tiêu',
    'cashew': 'Hạt điều',
    'rubber': 'Cao su',
    'cocoa': 'Cocoa',
    'cotton': 'Cotton',
}
COMMODITY_EMOJI = {
    'cocoa': 'CO', 'cotton': 'CT',
    'rice': '🌾', 'coffee': '☕', 'pepper': '🌶️', 'cashew': '🥜', 'rubber': '🌿',
}

# Palette: #FBF5DD · #E7E1B1 · #306D29 · #0D530E
COLORS = {
    'rice':   '#306D29',
    'coffee': '#8B5E3C',
    'pepper': '#C0392B',
    'cashew': '#B8860B',
    'rubber': '#2E8B57',
    'cocoa': '#7C4A2D',
    'cotton': '#4B7F9F',
}
CARD_GRADIENTS = {
    'rice':   'linear-gradient(135deg,#0D530E,#306D29)',
    'coffee': 'linear-gradient(135deg,#5c3a1e,#8B5E3C)',
    'pepper': 'linear-gradient(135deg,#7b0d0d,#C0392B)',
    'cashew': 'linear-gradient(135deg,#7a5200,#B8860B)',
    'rubber': 'linear-gradient(135deg,#1a5c38,#2E8B57)',
    'cocoa': 'linear-gradient(135deg,#4A2415,#7C4A2D)',
    'cotton': 'linear-gradient(135deg,#275066,#4B7F9F)',
}

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AgriPrice Vietnam",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Global CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ════════════════════════════════════════
   PREMIUM DARK THEME
   ════════════════════════════════════════ */

/* ── Main area ── */
.block-container {
    background: transparent !important;
    padding-top: 3.5rem !important;
}
.stApp {
    background-color: #0B0F19 !important;
    background-image: radial-gradient(circle at 15% 50%, rgba(16, 185, 129, 0.04), transparent 25%),
                      radial-gradient(circle at 85% 30%, rgba(59, 130, 246, 0.04), transparent 25%);
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #111827 !important;
    border-right: 1px solid rgba(255,255,255,0.05) !important;
}
[data-testid="stSidebar"] * { color: #F8FAFC !important; }
[data-testid="stSidebar"] .stMarkdown p { color: #94A3B8 !important; }

/* ── Typography ── */
h1 { 
    background: linear-gradient(90deg, #38BDF8, #818CF8, #34D399) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    font-weight: 800 !important; letter-spacing: -0.5px; 
}
h2, h3, h4 { color: #F8FAFC !important; font-weight: 700 !important; }
p, li { color: #CBD5E1 !important; }
label { color: #94A3B8 !important; font-weight: 600 !important; }

/* ── Metric card ── */
.mc {
    border-radius: 20px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 0.8rem;
    position: relative;
    overflow: hidden;
    background: rgba(30, 41, 59, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 4px 24px rgba(0,0,0,0.2);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.mc:hover { 
    transform: translateY(-4px); 
    box-shadow: 0 12px 32px rgba(0,0,0,0.4); 
    border: 1px solid rgba(255, 255, 255, 0.15);
}
.mc-emoji { 
    font-size: 3rem; position: absolute; right: 1rem; top: 1rem;
    opacity: 0.15; line-height: 1; filter: saturate(0) brightness(2);
}
.mc-label { 
    font-size: 0.75rem; text-transform: uppercase;
    letter-spacing: 1.5px; color: #94A3B8;
    margin-bottom: 0.4rem; position: relative; font-weight: 600;
}
.mc-value { 
    font-size: 1.7rem; font-weight: 800; color: #F8FAFC;
    letter-spacing: -0.5px; line-height: 1.1; position: relative; 
}
.mc-cur   { font-size: 0.8rem; font-weight: 500; color: #64748B; margin-left: 4px; }
.mc-change{ font-size: 0.85rem; margin-top: 0.5rem; font-weight: 600; position: relative; display: flex; align-items: center; gap: 4px;}
.mc-sub   { font-size: 0.75rem; color: #64748B;
            margin-top: 0.5rem; line-height: 1.6; position: relative; }
            
.badge {
    display: inline-flex; align-items: center; padding: 3px 10px; border-radius: 6px;
    font-size: 0.75rem; font-weight: 700; letter-spacing: 0.5px;
    margin-bottom: 0.4rem;
}
.badge-up   { background: rgba(16, 185, 129, 0.15); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.3); }
.badge-down { background: rgba(244, 63, 94, 0.15); color: #FB7185; border: 1px solid rgba(244, 63, 94, 0.3); }
.up   { color: #34D399; }
.down { color: #FB7185; }

/* ── Glass card ── */
.glass {
    background: rgba(30, 41, 59, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 24px;
    padding: 1.8rem;
    margin-bottom: 1.5rem;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    box-shadow: 0 4px 24px rgba(0,0,0,0.2);
}

.insight-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 1rem;
    margin: 0.5rem 0 1.5rem;
}
.insight-card {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px;
    padding: 1.2rem;
    box-shadow: 0 4px 16px rgba(0,0,0,0.1);
    transition: transform 0.2s ease;
}
.insight-card:hover { transform: translateY(-2px); border-color: rgba(255, 255, 255, 0.12); }
.insight-label {
    color: #94A3B8;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
}
.insight-value {
    color: #F8FAFC;
    font-size: 1.5rem;
    font-weight: 800;
    line-height: 1.1;
}
.insight-sub {
    color: #64748B;
    font-size: 0.8rem;
    margin-top: 0.4rem;
}
@media (max-width: 900px) {
    .insight-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 560px) {
    .insight-grid { grid-template-columns: 1fr; }
}

/* ── Page header banner ── */
.page-banner {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9));
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 1.5rem 2rem;
    margin-bottom: 2rem;
    display: flex; align-items: center; gap: 1.5rem;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}
.page-banner-icon { font-size: 3rem; filter: drop-shadow(0 4px 8px rgba(0,0,0,0.4)); }
.page-banner-title {
    font-size: 1.8rem; font-weight: 800;
    background: linear-gradient(90deg, #F8FAFC, #CBD5E1);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.page-banner-sub { font-size: 0.9rem; color: #94A3B8; margin-top: 0.2rem; }

/* ── Divider ── */
.fancy-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
    margin: 2rem 0;
    border: none;
}

/* ── Sidebar nav radio ── */
div[data-testid="stRadio"] > div { gap: 6px !important; }
div[data-testid="stRadio"] label {
    border-radius: 12px !important;
    padding: 10px 14px !important;
    transition: all 0.2s ease !important;
    color: #94A3B8 !important;
    border: 1px solid transparent !important;
}
div[data-testid="stRadio"] label:hover {
    background: rgba(255,255,255,0.05) !important;
    color: #F8FAFC !important;
}
div[data-testid="stRadio"] label[data-checked="true"] {
    background: rgba(56, 189, 248, 0.1) !important;
    border: 1px solid rgba(56, 189, 248, 0.2) !important;
    color: #38BDF8 !important;
}

/* ── Multiselect container ── */
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="base-input"],
[data-testid="stSidebar"] div[class*="multiselect"] {
    background: rgba(15, 23, 42, 0.5) !important;
    border-color: rgba(255,255,255,0.1) !important;
    border-radius: 12px !important;
}

/* ── Multiselect tags ── */
[data-testid="stSidebar"] span[data-baseweb="tag"] {
    background: rgba(56, 189, 248, 0.15) !important;
    border: 1px solid rgba(56, 189, 248, 0.3) !important;
    border-radius: 8px !important;
    color: #38BDF8 !important;
}
[data-testid="stSidebar"] span[data-baseweb="tag"] span,
[data-testid="stSidebar"] span[data-baseweb="tag"] button { color: #38BDF8 !important; }

/* ── Search inputs ── */
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] [data-baseweb="input"] {
    background: rgba(15, 23, 42, 0.5) !important;
    border-color: rgba(255,255,255,0.1) !important;
    color: #F8FAFC !important;
    border-radius: 8px !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0B0F19; }
::-webkit-scrollbar-thumb { background: #334155; border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: #475569; }

/* ── Buttons ── */
.stButton > button {
    background: rgba(15, 23, 42, 0.8) !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    color: #F8FAFC !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    background: rgba(56, 189, 248, 0.15) !important;
    border-color: rgba(56, 189, 248, 0.3) !important;
    color: #38BDF8 !important;
    transform: translateY(-1px) !important;
}

/* ── Expander ── */
details {
    background: rgba(15, 23, 42, 0.4) !important;
    border: 1px solid rgba(255,255,255,0.05) !important;
    border-radius: 12px !important;
}

/* ── Select Dropdown Options ── */
div[data-baseweb="popover"] > div {
    background-color: #1E293B !important;
}
div[data-baseweb="popover"] li {
    color: #F8FAFC !important;
    background-color: transparent !important;
}
div[data-baseweb="popover"] li:hover {
    background-color: rgba(56, 189, 248, 0.2) !important;
}

/* ── Chat messages & Input ── */
[data-testid="stChatMessage"] {
    background: rgba(30, 41, 59, 0.6) !important;
    border: 1px solid rgba(255,255,255,0.05) !important;
    border-radius: 14px !important;
    margin-bottom: 0.6rem !important;
    color: #F8FAFC !important;
}
[data-testid="stChatMessage"] * { color: #F8FAFC !important; }
[data-testid="stChatMessage"] p { color: #F8FAFC !important; }
[data-testid="stChatMessage"] code { color: #38BDF8 !important; background: rgba(0,0,0,0.2) !important; }

[data-testid="stBottomBlockContainer"] {
    background-color: #0B0F19 !important;
    padding-bottom: 1rem !important;
}
[data-testid="stChatInput"] {
    background-color: rgba(15, 23, 42, 0.8) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 12px !important;
}
[data-testid="stChatInput"] textarea { color: #F8FAFC !important; }
[data-testid="stChatInput"] svg { fill: #94A3B8 !important; }

/* ── Input / select / date ── */
input, select, textarea,
[data-baseweb="input"] input,
[data-baseweb="select"] {
    background: rgba(15, 23, 42, 0.8) !important;
    border-color: rgba(255,255,255,0.1) !important;
    color: #F8FAFC !important;
}

/* ── DataFrame ── */
[data-testid="stDataFrame"] { border-radius: 12px !important; overflow: hidden; }

/* ── Alerts ── */
.stAlert { border-radius: 12px !important; }

</style>
""", unsafe_allow_html=True)

# ─── Plotly dark theme ────────────────────────────────────────────────────────
PLOT_LAYOUT = dict(
    plot_bgcolor  = "rgba(15, 23, 42, 0.4)",
    paper_bgcolor = "rgba(0,0,0,0)",
    font          = dict(color="#94A3B8", family="Inter, sans-serif", size=12),
    legend        = dict(
        bgcolor     = "rgba(15, 23, 42, 0.8)",
        bordercolor = "rgba(255,255,255,0.1)",
        borderwidth = 1,
        font        = dict(size=12, color="#F8FAFC"),
    ),
    margin = dict(l=10, r=10, t=40, b=10),
    hoverlabel = dict(
        bgcolor     = "#1E293B",
        bordercolor = "rgba(255,255,255,0.15)",
        font_size   = 13,
        font_color  = "#F8FAFC",
    ),
)
def styled_axes(fig, height=420):
    fig.update_xaxes(
        gridcolor="rgba(255,255,255,0.05)", gridwidth=1,
        zerolinecolor="rgba(255,255,255,0.1)",
        tickfont=dict(color="#64748B"), title_font=dict(color="#94A3B8"),
        linecolor="rgba(255,255,255,0.1)",
    )
    fig.update_yaxes(
        gridcolor="rgba(255,255,255,0.05)", gridwidth=1,
        zerolinecolor="rgba(255,255,255,0.1)",
        tickfont=dict(color="#64748B"), title_font=dict(color="#94A3B8"),
        linecolor="rgba(255,255,255,0.1)",
    )
    fig.update_layout(height=height, **PLOT_LAYOUT)
    return fig

# ─── Database ─────────────────────────────────────────────────────────────────
def _token():
    try:    return st.secrets["MOTHERDUCK_TOKEN"]
    except: return os.getenv("MOTHERDUCK_TOKEN", "")

@st.cache_data(ttl=3600, show_spinner=False)
def load_prices() -> pd.DataFrame:
    con = duckdb.connect(f"md:agri_dwh?motherduck_token={_token()}")
    df  = con.execute("""
        SELECT f.price_date, f.commodity,
               f.price_usd_per_kg, f.price_change_pct,
               f.price_7d_avg, f.price_30d_avg,
               f.source, f.is_imputed,
               c.name_vi, c.category
        FROM gold.fact_price_daily f
        JOIN gold.dim_commodity c ON f.commodity_id = c.commodity_id
        ORDER BY f.price_date, f.commodity
    """).df()
    con.close()
    df["price_date"] = pd.to_datetime(df["price_date"])
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def load_forecast():
    try:
        con = duckdb.connect(f"md:agri_dwh?motherduck_token={_token()}")
        df  = con.execute("SELECT * FROM gold.forecast_lstm ORDER BY forecast_date,commodity").df()
        con.close()
        df["forecast_date"] = pd.to_datetime(df["forecast_date"])
        return df
    except: return None

@st.cache_data(ttl=600, show_spinner=False)
def load_alerts() -> pd.DataFrame:
    try:
        con = duckdb.connect(f"md:agri_dwh?motherduck_token={_token()}")
        df = con.execute("SELECT * FROM bronze.price_alerts ORDER BY created_at DESC LIMIT 5").df()
        con.close()
        return df
    except:
        return pd.DataFrame()

def normalize_price_rows(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["price_date"] = pd.to_datetime(df["price_date"])

    grouped = (
        df.groupby(["price_date", "commodity"], as_index=False)
        .agg({
            "price_usd_per_kg": "mean",
            "name_vi": "first",
            "category": "first",
        })
        .sort_values(["commodity", "price_date"])
        .reset_index(drop=True)
    )

    by_comm = grouped.groupby("commodity")["price_usd_per_kg"]
    grouped["price_change_pct"] = by_comm.pct_change() * 100
    grouped["price_7d_avg"] = by_comm.transform(lambda s: s.rolling(7, min_periods=1).mean())
    grouped["price_30d_avg"] = by_comm.transform(lambda s: s.rolling(30, min_periods=1).mean())
    return grouped

# ─── Load data ────────────────────────────────────────────────────────────────
with st.spinner(""):
    try:
        df_all  = load_prices()
    except Exception as e:
        st.error(f"❌ Không kết nối được MotherDuck: {e}")
        st.stop()

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center;padding:1.2rem 0 .6rem">
      <div style="filter:drop-shadow(0 2px 10px rgba(0,0,0,0.4))">
        <img src="data:image/png;base64,{LOGO_B64}" width="56" height="56" style="vertical-align:middle;">
      </div>
      <div style="font-size:1.15rem;font-weight:800;color:#FBF5DD;letter-spacing:-.3px;margin-top:.5rem;">
        AgriPrice Vietnam
      </div>
      <div style="font-size:.68rem;color:#a8c87a;margin-top:.2rem;letter-spacing:.5px;">
        DWH NHÓM 6 2025
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)

    page = st.radio("", [
        "Tổng quan",
        "Phân tích",
        "Dự báo",
        "Trợ lý AI",
    ], label_visibility="collapsed")


    st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:.72rem;color:#a8c87a;font-weight:700;letter-spacing:1.5px;margin-bottom:.6rem;">BỘ LỌC</div>', unsafe_allow_html=True)

    all_comms = sorted(df_all["commodity"].unique().tolist())
    selected  = st.multiselect(
        "Mặt hàng",
        options  = all_comms,
        default  = all_comms,
        format_func = lambda x: f"{COMMODITY_EMOJI.get(x,'')} {COMMODITY_VI.get(x,x)}",
    )

    min_d = df_all["price_date"].min().date()
    max_d = df_all["price_date"].max().date()
    period_preset = st.radio(
        "Khoảng thời gian",
        ["1 năm", "3 năm", "5 năm", "Tất cả", "Tùy chỉnh"],
        index=3,
        horizontal=True,
    )
    preset_years = {"1 năm": 1, "3 năm": 3, "5 năm": 5}
    start_default = min_d
    if period_preset in preset_years:
        start_default = max(
            min_d,
            (pd.Timestamp(max_d) - pd.DateOffset(years=preset_years[period_preset])).date(),
        )
    date_range = st.slider(
        "Chọn khoảng",
        min_value=min_d,
        max_value=max_d,
        value=(start_default, max_d),
        format="MM/YYYY",
        key=f"date_slider_{period_preset}",
    )

    currency = st.radio("Đơn vị tiền tệ", ["USD / kg", "VND / kg"])
    mult = USD_TO_VND if "VND" in currency else 1
    cur  = "VND"      if "VND" in currency else "USD"

    st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="font-size:.72rem;color:#a8c87a;line-height:2;">
      Dữ liệu đến: <b style="color:#E7E1B1">{max_d.strftime('%m/%Y')}</b><br>
      Nguồn: World Bank · Yahoo Finance<br>
      Cache: 1 giờ
    </div>
    """, unsafe_allow_html=True)

# ─── Guard ────────────────────────────────────────────────────────────────────
if not selected:
    st.warning("⚠️ Vui lòng chọn ít nhất 1 mặt hàng.")
    st.stop()

df_all_norm = normalize_price_rows(df_all)

s_dt = pd.Timestamp(date_range[0]) if len(date_range) >= 1 else df_all_norm["price_date"].min()
e_dt = pd.Timestamp(date_range[1]) if len(date_range) == 2 else df_all_norm["price_date"].max()

df = df_all_norm[
    df_all_norm["commodity"].isin(selected) &
    (df_all_norm["price_date"] >= s_dt) &
    (df_all_norm["price_date"] <= e_dt)
].copy()
if df.empty:
    st.warning("Không có dữ liệu trong bộ lọc hiện tại.")
    st.stop()

df["price"]     = df["price_usd_per_kg"] * mult
df["price_7d"]  = df["price_7d_avg"]    * mult
df["price_30d"] = df["price_30d_avg"]   * mult

def fp(v):
    return f"{v:,.0f}" if cur == "VND" else f"{v:.4f}"

def banner(icon, title, sub):
    """icon: emoji string."""
    img = f'<span style="font-size:2.2rem">{icon}</span>'
    st.markdown(f"""
    <div class="page-banner">
      <div class="page-banner-icon">{img}</div>
      <div>
        <div class="page-banner-title">{title}</div>
        <div class="page-banner-sub">{sub}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — TỔNG QUAN
# ══════════════════════════════════════════════════════════════════════════════
if page == "Tổng quan":
    alerts_df = load_alerts()
    if not alerts_df.empty:
        recent_alerts = alerts_df[alerts_df['alert_date'] >= pd.to_datetime(pd.Timestamp.now().date() - pd.Timedelta(days=3))]
        if not recent_alerts.empty:
            st.markdown("#### 🔔 Cảnh báo Biến động Giá")
            for idx, row in recent_alerts.iterrows():
                direction = "tăng" if row['pct_change'] > 0 else "giảm"
                st.warning(f"**{row['commodity'].upper()}** {direction} mạnh **{abs(row['pct_change']):.2f}%** vào ngày {row['alert_date']}. Phân tích AI: *{row['ai_comment']}*")
            st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)

    banner("🌾", "Tổng quan Giá Nông sản Việt Nam",
           f"Dữ liệu từ {s_dt.strftime('%m/%Y')} → {e_dt.strftime('%m/%Y')} · {len(selected)} mặt hàng")

    latest_rows = df.sort_values("price_date").groupby("commodity", as_index=False).tail(1)
    latest_date = df["price_date"].max()
    pulse = latest_rows.assign(abs_change=latest_rows["price_change_pct"].abs().fillna(0))
    strongest = pulse.sort_values("abs_change", ascending=False).iloc[0]
    avg_move = pulse["abs_change"].mean()
    strongest_name = f"{COMMODITY_EMOJI.get(strongest['commodity'],'')} {COMMODITY_VI.get(strongest['commodity'], strongest['commodity'])}"
    strongest_change = strongest["price_change_pct"]
    strongest_arrow = "▲" if (strongest_change or 0) >= 0 else "▼"

    st.markdown(f"""
    <div class="insight-grid">
      <div class="insight-card">
        <div class="insight-label">Cập nhật mới nhất</div>
        <div class="insight-value">{latest_date.strftime('%m/%Y')}</div>
        <div class="insight-sub">{len(df):,} điểm dữ liệu sau lọc</div>
      </div>
      <div class="insight-card">
        <div class="insight-label">Biến động mạnh nhất</div>
        <div class="insight-value">{strongest_name}</div>
        <div class="insight-sub">{strongest_arrow} {abs(strongest_change or 0):.2f}% so với kỳ trước</div>
      </div>
      <div class="insight-card">
        <div class="insight-label">Dao động trung bình</div>
        <div class="insight-value">{avg_move:.2f}%</div>
        <div class="insight-sub">Trên {len(latest_rows)} mặt hàng đang chọn</div>
      </div>
      <div class="insight-card">
        <div class="insight-label">Khoảng phân tích</div>
        <div class="insight-value">{s_dt.strftime('%m/%Y')} → {e_dt.strftime('%m/%Y')}</div>
        <div class="insight-sub">Đơn vị hiện tại: {cur}/kg</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Metric cards ──────────────────────────────────────────────────────────
    cols = st.columns(len(selected))
    for i, comm in enumerate(selected):
        df_c = df[df["commodity"] == comm].sort_values("price_date")
        if df_c.empty: continue
        lat        = df_c.iloc[-1]
        price_now  = lat["price"]
        chg        = lat["price_change_pct"]
        chg_value  = 0 if pd.isna(chg) else chg
        cutoff     = lat["price_date"] - pd.DateOffset(weeks=52)
        df52       = df_c[df_c["price_date"] >= cutoff]
        hi52, lo52 = df52["price"].max(), df52["price"].min()
        sign  = "up"  if chg_value >= 0 else "down"
        arrow = "▲"   if chg_value >= 0 else "▼"
        badge_cls = "badge-up" if chg_value >= 0 else "badge-down"
        ch_str = f"{arrow} {abs(chg_value):.2f}%"
        with cols[i]:
            st.markdown(f"""
            <div class="mc" style="background:{CARD_GRADIENTS.get(comm,'linear-gradient(135deg,#1e3a5f,#2d5a9e)')}">
              <div class="mc-emoji">{COMMODITY_EMOJI.get(comm,'')}</div>
              <div class="mc-label">{COMMODITY_VI.get(comm, comm).upper()}</div>
              <div class="mc-value">{fp(price_now)}<span class="mc-cur">{cur}/kg</span></div>
              <div class="mc-change">
                <span class="badge {badge_cls}">{ch_str}</span>
                <span style="color:rgba(255,255,255,.45);font-size:.7rem;margin-left:4px;">vs tháng trước</span>
              </div>
              <div class="mc-sub">
                Max 52T: <b style="color:rgba(255,255,255,.85)">{fp(hi52)}</b><br>
                Min 52T: <b style="color:rgba(255,255,255,.85)">{fp(lo52)}</b>
              </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)

    # ── Line chart (area + MA) ────────────────────────────────────────────────
    st.markdown("#### 📈 Biến động giá theo thời gian")
    fig = go.Figure()
    for comm in selected:
        df_c  = df[df["commodity"] == comm].sort_values("price_date")
        name  = f"{COMMODITY_EMOJI.get(comm,'')} {COMMODITY_VI.get(comm,comm)}"
        color = COLORS.get(comm, "#888")

        # Area fill
        fig.add_trace(go.Scatter(
            x=df_c["price_date"], y=df_c["price"],
            fill="tozeroy", fillcolor=f"rgba({','.join(str(int(color.lstrip('#')[i:i+2],16)) for i in (0,2,4))},0.08)",
            line=dict(width=0), showlegend=False, hoverinfo="skip",
        ))
        # Main line
        fig.add_trace(go.Scatter(
            x=df_c["price_date"], y=df_c["price"], name=name,
            line=dict(color=color, width=2.5),
            mode="lines",
            hovertemplate=f"<b>{name}</b><br>%{{x|%m/%Y}}<br>💰 %{{y:,.4f}} {cur}/kg<extra></extra>",
        ))
        # MA30 dotted
        fig.add_trace(go.Scatter(
            x=df_c["price_date"], y=df_c["price_30d"],
            line=dict(color=color, width=1.2, dash="dot"),
            opacity=0.5, showlegend=False, hoverinfo="skip",
        ))

    fig = styled_axes(fig, height=440)
    fig.update_layout(
        hovermode="x unified",
        legend=dict(orientation="h", y=1.04, x=1, xanchor="right"),
        xaxis_title="", yaxis_title=f"Giá ({cur}/kg)",
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Data table ────────────────────────────────────────────────────────────
    with st.expander("📋 Xem & tải bảng dữ liệu"):
        tbl = df[["price_date","commodity","price","price_change_pct","price_7d","price_30d"]].copy()
        tbl.columns = ["Tháng","Mặt hàng",f"Giá ({cur}/kg)","% Thay đổi","TB 7 ngày","TB 30 ngày"]
        tbl["Tháng"]    = tbl["Tháng"].dt.strftime("%m/%Y")
        tbl["Mặt hàng"] = tbl["Mặt hàng"].map(lambda x: f"{COMMODITY_EMOJI.get(x,'')} {COMMODITY_VI.get(x,x)}")
        st.dataframe(tbl.sort_values("Tháng", ascending=False), use_container_width=True, height=280)
        st.download_button("Tải CSV", tbl.to_csv(index=False).encode(),
                           "gia_nong_san.csv", "text/csv")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — PHÂN TÍCH
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Phân tích":
    banner("📊", "Phân tích Thị trường",
           "Heatmap mùa vụ · So sánh mặt hàng · Tương quan giá")

    # ── Row 1: Heatmap + Bar ──────────────────────────────────────────────────
    c_left, c_right = st.columns([1.4, 1], gap="large")

    with c_left:
        st.markdown("#### 📦 Biên độ dao động Giá")
        heat_comm = st.selectbox("Mặt hàng",selected,
            format_func=lambda x:f"{COMMODITY_EMOJI.get(x,'')} {COMMODITY_VI.get(x,x)}",
            key="heat_sel", label_visibility="collapsed")
        df_h = df[df["commodity"] == heat_comm].copy()
        df_h["year"]  = df_h["price_date"].dt.year
        # Lọc 10 năm gần nhất
        df_h = df_h[df_h["year"] >= df_h["year"].max() - 10]
        
        color = COLORS.get(heat_comm, "#06b6d4")
        fig_h = go.Figure(go.Box(
            x=df_h["year"], y=df_h["price"],
            name="Giá", marker_color=color,
            boxmean=True,
            hovertemplate="Năm %{x}<br>Giá: %{y:,.4f} "+cur+"/kg<extra></extra>"
        ))
        fig_h = styled_axes(fig_h, height=290)
        fig_h.update_layout(
            xaxis_title="", yaxis_title=f"{cur}/kg",
            title=dict(text=f"Biên độ giá {COMMODITY_VI.get(heat_comm,'')} (10 năm)", font=dict(size=13, color="#94a3b8"))
        )
        fig_h.update_xaxes(type='category')
        st.plotly_chart(fig_h, use_container_width=True)

    with c_right:
        st.markdown("#### 📊 Giá hiện tại")
        df_bar = df.sort_values("price_date").groupby("commodity").last().reset_index()
        df_bar["label"] = df_bar["commodity"].map(lambda x: f"{COMMODITY_EMOJI.get(x,'')} {COMMODITY_VI.get(x,x)}")
        df_bar = df_bar.sort_values("price", ascending=True)

        fig_b = go.Figure(go.Bar(
            x=df_bar["price"], y=df_bar["label"],
            orientation="h",
            marker=dict(
                color=[COLORS.get(c,"#888") for c in df_bar["commodity"]],
                line=dict(width=0),
                opacity=0.9,
            ),
            text=[fp(v) for v in df_bar["price"]],
            textposition="outside",
            textfont=dict(color="#94a3b8", size=12),
            hovertemplate="%{y}: %{x:,.4f} "+cur+"/kg<extra></extra>",
        ))
        fig_b = styled_axes(fig_b, height=290)
        fig_b.update_layout(
            xaxis_title=f"{cur}/kg", yaxis_title="", showlegend=False,
            title=dict(text="Tháng gần nhất", font=dict(size=13, color="#94a3b8")),
        )
        fig_b.update_xaxes(showgrid=False)
        st.plotly_chart(fig_b, use_container_width=True)

    st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)

    # ── Row 2: Scatter tương quan ─────────────────────────────────────────────
    st.markdown("#### 🔗 Tương quan Giá giữa 2 Mặt hàng")
    if len(selected) < 2:
        st.info("Chọn ít nhất 2 mặt hàng ở sidebar để xem tương quan.")
    else:
        col1, col2, _ = st.columns([1,1,2])
        x_c = col1.selectbox("Trục X", selected, index=0,
            format_func=lambda x:f"{COMMODITY_EMOJI.get(x,'')} {COMMODITY_VI.get(x,x)}", key="sc_x")
        y_c = col2.selectbox("Trục Y", [c for c in selected if c != x_c], index=0,
            format_func=lambda x:f"{COMMODITY_EMOJI.get(x,'')} {COMMODITY_VI.get(x,x)}", key="sc_y")

        df_x = df[df["commodity"]==x_c][["price_date","price"]].rename(columns={"price":"px"})
        df_y = df[df["commodity"]==y_c][["price_date","price"]].rename(columns={"price":"py"})
        dfs  = df_x.merge(df_y, on="price_date").dropna()

        if not dfs.empty:
            corr  = dfs["px"].corr(dfs["py"])
            z     = np.polyfit(dfs["px"], dfs["py"], 1)
            xline = np.linspace(dfs["px"].min(), dfs["px"].max(), 100)
            cx    = COLORS.get(x_c,"#38bdf8")
            r,g,b = tuple(int(cx.lstrip('#')[i:i+2],16) for i in (0,2,4))

            fig_s = go.Figure()
            fig_s.add_trace(go.Scatter(
                x=dfs["px"], y=dfs["py"], mode="markers",
                marker=dict(color=cx, size=9, opacity=0.75,
                            line=dict(color="rgba(255,255,255,.2)", width=1)),
                text=dfs["price_date"].dt.strftime("%m/%Y"),
                hovertemplate="Tháng: %{text}<br>X: %{x:.4f}<br>Y: %{y:.4f}<extra></extra>",
                name="Quan sát",
            ))
            fig_s.add_trace(go.Scatter(
                x=xline, y=np.poly1d(z)(xline), mode="lines",
                line=dict(color=f"rgba({r},{g},{b},.5)", dash="dash", width=2),
                name=f"Xu hướng  r={corr:.2f}",
            ))
            fig_s = styled_axes(fig_s, height=380)
            fig_s.update_layout(
                xaxis_title=f"{COMMODITY_VI.get(x_c,x_c)} ({cur}/kg)",
                yaxis_title=f"{COMMODITY_VI.get(y_c,y_c)} ({cur}/kg)",
                title=dict(text=f"Tương quan Pearson: r = {corr:.3f}  "
                    f"({'mạnh' if abs(corr)>.7 else 'trung bình' if abs(corr)>.4 else 'yếu'})",
                    font=dict(size=13, color="#94a3b8")),
            )
            st.plotly_chart(fig_s, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — DỰ BÁO
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Dự báo":
    banner("🔮","Dự báo Giá Nông sản","ARIMA · LSTM · Confidence Interval 95%")

    df_fc = load_forecast()

    if df_fc is None:
        # ── Placeholder đẹp ──────────────────────────────────────────────────
        st.markdown("""
        <div class="glass" style="text-align:center;padding:2rem;">
          <div style="font-size:3rem;margin-bottom:.5rem">⏳</div>
          <div style="font-size:1.1rem;font-weight:700;color:#e2e8f0;">Đang chờ MEM ML Engineer</div>
          <div style="color:#64748b;font-size:.85rem;margin-top:.4rem;">
            Bảng <code>gold.forecast_lstm</code> chưa có dữ liệu.<br>
            Trang này sẽ tự động hiển thị khi model ARIMA/LSTM hoàn thành.
          </div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        for col, icon, title, desc in [
            (col1,"🧠","LSTM Neural Network","Target MAPE < 10%"),
            (col2,"📈","ARIMA Baseline","Mô hình chuỗi thời gian"),
            (col3,"📊","Confidence Interval","Độ tin cậy 95%"),
        ]:
            with col:
                st.markdown(f"""
                <div class="glass" style="text-align:center;">
                  <div style="font-size:2rem">{icon}</div>
                  <div style="font-weight:700;color:#e2e8f0;font-size:.95rem;">{title}</div>
                  <div style="color:#64748b;font-size:.78rem;margin-top:.25rem;">{desc}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)
        st.markdown("#### 👁️ Preview bố cục (dữ liệu minh hoạ)")

        fig_p = go.Figure()
        rng   = np.random.default_rng(42)
        for comm in selected[:3]:
            df_c = df[df["commodity"]==comm].sort_values("price_date").tail(18)
            if df_c.empty: continue
            name  = f"{COMMODITY_EMOJI.get(comm,'')} {COMMODITY_VI.get(comm,comm)}"
            color = COLORS.get(comm,"#888")
            r2,g2,b2 = tuple(int(color.lstrip('#')[i:i+2],16) for i in (0,2,4))
            last_p = df_c["price"].iloc[-1]
            fut    = pd.date_range(df_c["price_date"].max(), periods=7, freq="MS")[1:]
            fc     = [last_p*(1+rng.uniform(-0.02,0.04)) for _ in range(6)]
            ci_up  = [v*1.09 for v in fc]
            ci_lo  = [v*0.91 for v in fc]

            # Historical
            fig_p.add_trace(go.Scatter(
                x=df_c["price_date"], y=df_c["price"], name=name,
                line=dict(color=color, width=2.5),
            ))
            # Forecast dash
            fig_p.add_trace(go.Scatter(
                x=fut, y=fc, name=f"{name} (dự báo)",
                line=dict(color=color, width=2, dash="dash"),
            ))
            # CI band
            fig_p.add_trace(go.Scatter(
                x=list(fut)+list(fut[::-1]),
                y=ci_up+ci_lo[::-1],
                fill="toself",
                fillcolor=f"rgba({r2},{g2},{b2},0.12)",
                line=dict(color="rgba(0,0,0,0)"),
                showlegend=False,
            ))

        fig_p.add_vline(x=df["price_date"].max(), line_dash="dot",
            line_color="rgba(255,255,255,.3)",
            annotation_text="Hôm nay", annotation_font_color="#94a3b8")
        fig_p = styled_axes(fig_p, height=430)
        fig_p.update_layout(xaxis_title="", yaxis_title=f"Giá ({cur}/kg)",
            title=dict(text="Minh hoạ layout — dữ liệu thật sẽ thay thế khi MEM ML hoàn thành",
                       font=dict(size=12, color="#64748b")))
        st.plotly_chart(fig_p, use_container_width=True)

    else:
        st.success(f"✅ Đã có {len(df_fc)} bản ghi dự báo bằng Machine Learning")
        fc_c = st.selectbox("Mặt hàng", selected,
            format_func=lambda x:f"{COMMODITY_EMOJI.get(x,'')} {COMMODITY_VI.get(x,x)}")
        df_h = df[df["commodity"]==fc_c].sort_values("price_date").tail(24)
        df_f = df_fc[df_fc["commodity"]==fc_c].sort_values("forecast_date")
        
        if not df_h.empty and not df_f.empty:
            last_h = df_h.iloc[-1]
            last_price = last_h["price"]
            
            # Prepend history to forecast to close the visual gap
            fut_dates = [last_h["price_date"]] + df_f["forecast_date"].tolist()
            fut_prices = [last_price] + (df_f["predicted_price"] * mult).tolist()
            ci_uppers = [last_price] + (df_f["ci_upper"] * mult).tolist()
            ci_lowers = [last_price] + (df_f["ci_lower"] * mult).tolist()
            
            # Insights
            fc_last = fut_prices[-1]
            pct_change = (fc_last - last_price) / last_price * 100
            trend = "Tăng" if pct_change > 0 else "Giảm"
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Giá hiện tại", f"{last_price:,.2f} {cur}/kg")
            with c2:
                st.metric("Dự báo (cuối kỳ 6T)", f"{fc_last:,.2f} {cur}/kg", f"{pct_change:+.2f}%")
            
            color = COLORS.get(fc_c,"#06b6d4")
            r2,g2,b2 = tuple(int(color.lstrip('#')[i:i+2],16) for i in (0,2,4))

            fig_f = go.Figure()
            fig_f.add_trace(go.Scatter(x=df_h["price_date"],y=df_h["price"],
                name="Lịch sử", line=dict(color=color,width=2.5)))
            fig_f.add_trace(go.Scatter(x=fut_dates, y=fut_prices,
                name="Dự báo LSTM", line=dict(color="#f59e0b",width=2.5,dash="dash")))
            if "ci_upper" in df_f.columns:
                fig_f.add_trace(go.Scatter(
                    x=fut_dates + fut_dates[::-1],
                    y=ci_uppers + ci_lowers[::-1],
                    fill="toself", fillcolor=f"rgba({r2},{g2},{b2},0.12)",
                    line=dict(color="rgba(0,0,0,0)"), name="CI 95%"))
            fig_f.add_vline(x=last_h["price_date"], line_dash="dot",
                line_color="rgba(255,255,255,.3)")
            fig_f = styled_axes(fig_f, height=430)
            fig_f.update_layout(yaxis_title=f"Giá ({cur}/kg)")
            st.plotly_chart(fig_f, use_container_width=True)
            
            if abs(pct_change) > 5:
                st.info(f"💡 **Insight:** Mô hình AI nhận định giá {COMMODITY_VI.get(fc_c,fc_c)} có xu hướng **{trend} khá rõ** trong thời gian tới. Nên theo dõi sát sao chiến lược mua/bán.")
            else:
                st.info(f"💡 **Insight:** Giá {COMMODITY_VI.get(fc_c,fc_c)} dự kiến sẽ đi ngang (sideway) hoặc chỉ biến động nhẹ. Thị trường tương đối bình ổn.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — TRỢ LÝ AI
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Trợ lý AI":
    from genbi_chat import render_genbi_page
    render_genbi_page(df_all_norm, cur, mult)
