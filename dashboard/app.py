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
   PALETTE  #FBF5DD · #E7E1B1 · #306D29 · #0D530E
   Main area: cream/light — Sidebar: dark green
   ════════════════════════════════════════ */

/* ── Main area: để Streamlit tự handle light/dark ── */
.block-container {
    background: transparent !important;
    padding-top: 1.5rem !important;
}

/* ── Sidebar: luôn xanh lá đậm (đẹp trong cả 2 mode) ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D530E 0%, #1e6b20 50%, #306D29 100%) !important;
    border-right: 2px solid #0a3d0c !important;
}
[data-testid="stSidebar"] * { color: #E7E1B1 !important; }
[data-testid="stSidebar"] .stMarkdown p { color: #c8c49a !important; }

/* ── Typography ── */
h1 { background: linear-gradient(90deg,#0D530E,#306D29,#5a8a2a) !important;
     -webkit-background-clip: text !important;
     -webkit-text-fill-color: transparent !important;
     font-weight: 800 !important; letter-spacing: -0.5px; }
h2 { color: #0D530E !important; font-weight: 700 !important; }
h3, h4 { color: #306D29 !important; font-weight: 600 !important; }
p, li { color: #3d5c2e !important; }
label { color: #306D29 !important; }

/* ── Metric card — FIX: bỏ backdrop-filter khỏi ::before để text không bị mờ ── */
.mc {
    border-radius: 16px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 0.6rem;
    position: relative;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5),
                inset 0 1px 0 rgba(255,255,255,0.15);
    transition: transform .2s ease, box-shadow .2s ease;
}
.mc:hover { transform: translateY(-3px); box-shadow: 0 20px 48px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.2); }
/* Shine effect ở góc trên — không blur text */
.mc::after {
    content: '';
    position: absolute; top: -40%; left: -40%;
    width: 80%; height: 80%;
    background: radial-gradient(circle, rgba(255,255,255,0.18) 0%, transparent 70%);
    pointer-events: none;
}
.mc-emoji { font-size: 2.5rem; position: absolute; right: 1rem; top: 0.8rem;
            opacity: .2; line-height: 1; }
.mc-label { font-size: 0.72rem; text-transform: uppercase;
            letter-spacing: 1.5px; color: rgba(255,255,255,0.65);
            margin-bottom: .3rem; position: relative; }
.mc-value { font-size: 1.55rem; font-weight: 800; color: #ffffff;
            letter-spacing: -0.5px; line-height: 1.1; position: relative; }
.mc-cur   { font-size: .75rem; font-weight: 400; opacity: .7; margin-left: 3px; }
.mc-change{ font-size: 0.8rem; margin-top: .35rem; font-weight: 600; position: relative; }
.mc-sub   { font-size: 0.7rem; color: rgba(255,255,255,.5);
            margin-top: .45rem; line-height: 1.7; position: relative; }
.up   { color: #4ade80; }
.down { color: #f87171; }
.badge {
    display: inline-block; padding: 2px 10px; border-radius: 99px;
    font-size: .68rem; font-weight: 700; letter-spacing: .5px;
    margin-bottom: .3rem;
}
.badge-up   { background: rgba(13,83,14,.15);  color: #1a6b1c; border: 1px solid rgba(13,83,14,.3); }
.badge-down { background: rgba(192,57,43,.12);  color: #a93226; border: 1px solid rgba(192,57,43,.3); }
.up   { color: #1a6b1c; }
.down { color: #a93226; }

/* ── Glass card ── */
.glass {
    background: rgba(231,225,177,0.25);
    border: 1px solid rgba(48,109,41,0.2);
    border-radius: 20px;
    padding: 1.5rem 1.8rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 20px rgba(13,83,14,0.08);
}

.insight-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: .8rem;
    margin: .2rem 0 1.2rem;
}
.insight-card {
    background: linear-gradient(135deg, rgba(251,245,221,.92), rgba(231,225,177,.42));
    border: 1px solid rgba(48,109,41,.22);
    border-radius: 14px;
    padding: .95rem 1rem;
    box-shadow: 0 8px 24px rgba(13,83,14,.08);
}
.insight-label {
    color: #5a7a3a;
    font-size: .68rem;
    font-weight: 800;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    margin-bottom: .35rem;
}
.insight-value {
    color: #0D530E;
    font-size: 1.35rem;
    font-weight: 850;
    line-height: 1.1;
}
.insight-sub {
    color: #5a7a3a;
    font-size: .76rem;
    margin-top: .35rem;
}
@media (max-width: 900px) {
    .insight-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 560px) {
    .insight-grid { grid-template-columns: 1fr; }
}

/* ── Page header banner ── */
.page-banner {
    background: linear-gradient(120deg, rgba(231,225,177,.6), rgba(244,240,220,.8));
    border: 1.5px solid rgba(48,109,41,0.25);
    border-radius: 16px;
    padding: 1.2rem 1.8rem;
    margin-bottom: 1.5rem;
    display: flex; align-items: center; gap: 1rem;
    box-shadow: 0 2px 12px rgba(13,83,14,0.08);
}
.page-banner-icon { font-size: 2.4rem; }
.page-banner-title {
    font-size: 1.5rem; font-weight: 800;
    background: linear-gradient(90deg, #0D530E, #306D29);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.page-banner-sub { font-size: .8rem; color: #5a7a3a; margin-top: .1rem; }

/* ── Divider ── */
.fancy-divider {
    height: 1.5px;
    background: linear-gradient(90deg, transparent, rgba(48,109,41,.4), transparent);
    margin: 1.5rem 0;
    border: none;
}

/* ── Sidebar nav radio ── */
div[data-testid="stRadio"] > div { gap: 4px !important; }
div[data-testid="stRadio"] label {
    border-radius: 10px !important;
    padding: 8px 12px !important;
    transition: background .15s !important;
    color: #E7E1B1 !important;
}
div[data-testid="stRadio"] label:hover {
    background: rgba(231,225,177,.15) !important;
}
div[data-testid="stRadio"] label[data-checked="true"] {
    background: rgba(251,245,221,.2) !important;
}

/* ── Multiselect container (trong sidebar) ── */
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="base-input"],
[data-testid="stSidebar"] div[class*="multiselect"] {
    background: rgba(13,83,14,0.55) !important;
    border-color: rgba(231,225,177,0.3) !important;
    border-radius: 10px !important;
}

/* ── Multiselect tags ── */
[data-testid="stSidebar"] span[data-baseweb="tag"] {
    background: rgba(231,225,177,0.2) !important;
    border: 1px solid rgba(231,225,177,0.4) !important;
    border-radius: 8px !important;
    color: #E7E1B1 !important;
}
[data-testid="stSidebar"] span[data-baseweb="tag"] span,
[data-testid="stSidebar"] span[data-baseweb="tag"] button { color: #E7E1B1 !important; }

/* ── Date input & radio trong sidebar ── */
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] [data-baseweb="input"] {
    background: rgba(13,83,14,0.55) !important;
    border-color: rgba(231,225,177,0.3) !important;
    color: #E7E1B1 !important;
    border-radius: 8px !important;
}

/* ── Buttons ── */
.stButton > button {
    background: rgba(48,109,41,.12) !important;
    border: 1.5px solid rgba(48,109,41,.35) !important;
    color: #0D530E !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    transition: all .2s !important;
}
.stButton > button:hover {
    background: rgba(48,109,41,.22) !important;
    border-color: #306D29 !important;
    transform: translateY(-1px) !important;
}

/* ── Download button ── */
.stDownloadButton > button {
    background: linear-gradient(135deg, rgba(13,83,14,.15), rgba(48,109,41,.1)) !important;
    border: 1.5px solid rgba(48,109,41,.3) !important;
    color: #0D530E !important;
    border-radius: 10px !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #E7E1B1; }
::-webkit-scrollbar-thumb { background: #306D29; border-radius: 99px; }

/* ── Expander ── */
details {
    background: rgba(231,225,177,.3) !important;
    border: 1px solid rgba(48,109,41,.2) !important;
    border-radius: 12px !important;
}

/* ── Chat messages ── */
[data-testid="stChatMessage"] {
    background: rgba(244,240,220,.8) !important;
    border: 1px solid rgba(48,109,41,.15) !important;
    border-radius: 14px !important;
    margin-bottom: .6rem !important;
}

/* ── Alerts ── */
.stAlert { border-radius: 12px !important; }

/* ── Input / select / date ── */
input, select, textarea,
[data-baseweb="input"] input,
[data-baseweb="select"] {
    background: #FBF5DD !important;
    border-color: rgba(48,109,41,.3) !important;
    color: #0D530E !important;
}

/* ── DataFrame ── */
[data-testid="stDataFrame"] { border-radius: 12px !important; overflow: hidden; }

/* ── Scrollbar (sidebar) ── */
[data-testid="stSidebar"] ::-webkit-scrollbar-track { background: #0D530E; }
[data-testid="stSidebar"] ::-webkit-scrollbar-thumb { background: #E7E1B1; }
</style>
""", unsafe_allow_html=True)

# ─── Plotly dark theme ────────────────────────────────────────────────────────
PLOT_LAYOUT = dict(
    plot_bgcolor  = "rgba(244,240,220,0.5)",
    paper_bgcolor = "rgba(0,0,0,0)",
    font          = dict(color="#3d5c2e", family="Inter, sans-serif", size=12),
    legend        = dict(
        bgcolor     = "rgba(251,245,221,0.9)",
        bordercolor = "rgba(48,109,41,0.3)",
        borderwidth = 1,
        font        = dict(size=12, color="#0D530E"),
    ),
    margin = dict(l=10, r=10, t=40, b=10),
    hoverlabel = dict(
        bgcolor     = "#FBF5DD",
        bordercolor = "rgba(48,109,41,.5)",
        font_size   = 13,
        font_color  = "#0D530E",
    ),
)
def styled_axes(fig, height=420):
    fig.update_xaxes(
        gridcolor="rgba(48,109,41,0.12)", gridwidth=1,
        zerolinecolor="rgba(48,109,41,0.2)",
        tickfont=dict(color="#5a7a3a"), title_font=dict(color="#306D29"),
        linecolor="rgba(48,109,41,0.2)",
    )
    fig.update_yaxes(
        gridcolor="rgba(48,109,41,0.12)", gridwidth=1,
        zerolinecolor="rgba(48,109,41,0.2)",
        tickfont=dict(color="#5a7a3a"), title_font=dict(color="#306D29"),
        linecolor="rgba(48,109,41,0.2)",
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
        DWH NHÓM 6 · 2025
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
        st.markdown("#### 🗓️ Heatmap Mùa vụ")
        heat_comm = st.selectbox("Mặt hàng",selected,
            format_func=lambda x:f"{COMMODITY_EMOJI.get(x,'')} {COMMODITY_VI.get(x,x)}",
            key="heat_sel", label_visibility="collapsed")
        df_h = df[df["commodity"] == heat_comm].copy()
        df_h["year"]  = df_h["price_date"].dt.year
        df_h["month"] = df_h["price_date"].dt.month
        pivot = df_h.pivot_table(index="year", columns="month", values="price", aggfunc="mean")
        pivot.columns = ["T1","T2","T3","T4","T5","T6","T7","T8","T9","T10","T11","T12"][:len(pivot.columns)]

        color = COLORS.get(heat_comm, "#06b6d4")
        r,g,b = tuple(int(color.lstrip('#')[i:i+2],16) for i in (0,2,4))
        fig_h = go.Figure(go.Heatmap(
            z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
            colorscale=[
                [0,   f"rgba({r},{g},{b},0.1)"],
                [0.5, f"rgba({r},{g},{b},0.55)"],
                [1,   f"rgba({r},{g},{b},1)"],
            ],
            text=[[f"{v:.3f}" for v in row] for row in pivot.values],
            texttemplate="%{text}", textfont=dict(size=11, color="white"),
            hoverongaps=False,
            hovertemplate="Năm %{y} · %{x}<br>Giá: %{z:.4f} "+cur+"/kg<extra></extra>",
        ))
        fig_h = styled_axes(fig_h, height=290)
        fig_h.update_layout(title=dict(text=f"Giá {COMMODITY_VI.get(heat_comm,'')} (mùa vụ)", font=dict(size=13, color="#94a3b8")))
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
        st.success(f"✅ Đã có {len(df_fc)} bản ghi dự báo")
        fc_c = st.selectbox("Mặt hàng", selected,
            format_func=lambda x:f"{COMMODITY_EMOJI.get(x,'')} {COMMODITY_VI.get(x,x)}")
        df_h = df[df["commodity"]==fc_c].sort_values("price_date").tail(24)
        df_f = df_fc[df_fc["commodity"]==fc_c].sort_values("forecast_date")
        color = COLORS.get(fc_c,"#06b6d4")
        r2,g2,b2 = tuple(int(color.lstrip('#')[i:i+2],16) for i in (0,2,4))

        fig_f = go.Figure()
        fig_f.add_trace(go.Scatter(x=df_h["price_date"],y=df_h["price"],
            name="Lịch sử", line=dict(color=color,width=2.5)))
        fig_f.add_trace(go.Scatter(x=df_f["forecast_date"],y=df_f["predicted_price"]*mult,
            name="Dự báo LSTM", line=dict(color="#f59e0b",width=2.5,dash="dash")))
        if "ci_upper" in df_f.columns:
            fig_f.add_trace(go.Scatter(
                x=list(df_f["forecast_date"])+list(df_f["forecast_date"][::-1]),
                y=list(df_f["ci_upper"]*mult)+list(df_f["ci_lower"][::-1]*mult),
                fill="toself", fillcolor=f"rgba({r2},{g2},{b2},0.12)",
                line=dict(color="rgba(0,0,0,0)"), name="CI 95%"))
        fig_f.add_vline(x=df_h["price_date"].max(), line_dash="dot",
            line_color="rgba(255,255,255,.3)")
        fig_f = styled_axes(fig_f, height=430)
        fig_f.update_layout(yaxis_title=f"Giá ({cur}/kg)")
        st.plotly_chart(fig_f, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — TRỢ LÝ AI
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Trợ lý AI":
    from genbi_chat import render_genbi_page
    render_genbi_page(df_all_norm, cur, mult)
