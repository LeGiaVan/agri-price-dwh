import streamlit as st
import pandas as pd
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

COMMODITY_VI = {
    'rice': 'Gạo', 'coffee': 'Cà phê',
    'pepper': 'Tiêu', 'cashew': 'Hạt điều', 'rubber': 'Cao su',
}
COMMODITY_EMOJI = {
    'rice': '🌾', 'coffee': '☕', 'pepper': '🌶️', 'cashew': '🥜', 'rubber': '🌿',
}

SAMPLE_QUESTIONS = [
    "Giá cà phê tháng tới có xu hướng gì?",
    "Nên nhập thêm mặt hàng nào?",
    "Mặt hàng nào biến động nhiều nhất?",
    "So sánh giá gạo và cao su năm 2024?",
    "Phân tích thị trường tiêu hiện tại?",
]


def get_market_summary(df: pd.DataFrame, cur: str, mult: float) -> str:
    """Tóm tắt top 5 mặt hàng biến động nhiều nhất để làm context cho AI."""
    if df.empty:
        return "Không có dữ liệu thị trường."

    latest = df.sort_values("price_date").groupby("commodity").last().reset_index()
    latest["abs_change"] = latest["price_change_pct"].abs().fillna(0)
    top5 = latest.nlargest(5, "abs_change")
    ref_date = latest["price_date"].max().strftime("%m/%Y")

    lines = [
        f"DỮ LIỆU THỊ TRƯỜNG NÔNG SẢN VIỆT NAM — {ref_date}",
        "=" * 50,
    ]
    for _, row in top5.iterrows():
        name   = COMMODITY_VI.get(row["commodity"], row["commodity"])
        emoji  = COMMODITY_EMOJI.get(row["commodity"], "")
        price  = row["price_usd_per_kg"] * mult
        change = row["price_change_pct"]
        sign   = "▲" if (change or 0) >= 0 else "▼"
        lines.append(
            f"{emoji} {name}: {price:.4f} {cur}/kg  "
            f"({sign}{abs(change or 0):.2f}% so với tháng trước)"
        )

    # Thêm context tổng quan
    all_latest = latest.copy()
    all_latest["price"] = all_latest["price_usd_per_kg"] * mult
    lines += [
        "",
        "TẤT CẢ MẶT HÀNG (giá hiện tại):",
    ]
    for _, row in all_latest.sort_values("price", ascending=False).iterrows():
        name  = COMMODITY_VI.get(row["commodity"], row["commodity"])
        emoji = COMMODITY_EMOJI.get(row["commodity"], "")
        lines.append(f"  {emoji} {name}: {row['price']:.4f} {cur}/kg")

    lines += [
        "",
        f"Dữ liệu lịch sử: {df['price_date'].min().strftime('%m/%Y')} → {df['price_date'].max().strftime('%m/%Y')}",
        "Nguồn: World Bank & Yahoo Finance",
        "5 mặt hàng xuất khẩu chủ lực của Việt Nam: gạo, cà phê, tiêu, hạt điều, cao su",
    ]
    return "\n".join(lines)


def call_groq(user_prompt: str, market_context: str, history: list) -> str:
    """Gọi Groq API với context thị trường và lịch sử chat."""
    api_key = os.getenv("GROQ_API_KEY")
    try:
        api_key = api_key or st.secrets["GROQ_API_KEY"]
    except Exception:
        pass
    if not api_key:
        return "❌ Chưa cấu hình GROQ_API_KEY trong `.env` hoặc Streamlit Secrets."

    client = Groq(api_key=api_key)

    system_prompt = f"""Bạn là chuyên gia phân tích thị trường nông sản Việt Nam với hơn 10 năm kinh nghiệm.
Bạn am hiểu sâu về 5 mặt hàng xuất khẩu chủ lực: gạo, cà phê, tiêu, hạt điều và cao su.

Dưới đây là dữ liệu thị trường thực tế (cập nhật mới nhất):
{market_context}

Nguyên tắc trả lời:
- Luôn trả lời bằng tiếng Việt, ngắn gọn và chuyên nghiệp
- Dựa vào số liệu thực tế trên để phân tích, KHÔNG bịa đặt số liệu
- Nêu rõ xu hướng, rủi ro và cơ hội nếu phù hợp
- Kết thúc bằng 1 khuyến nghị cụ thể nếu người dùng hỏi về quyết định kinh doanh
- Dùng emoji phù hợp để dễ đọc"""

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-6:]:  # Giữ 6 lượt gần nhất
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_prompt})

    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.65,
            max_tokens=900,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"❌ Lỗi Groq API: {e}"


def render_genbi_page(df_all: pd.DataFrame, cur: str, mult: float):
    """Render toàn bộ trang GenBI."""
    st.title("🤖 Trợ lý AI Thị trường Nông sản")
    st.caption("Phân tích & tư vấn thị trường · Powered by **Groq** (Llama 3.3 70B)")

    # ── Market context ────────────────────────────────────────────────────────
    market_ctx = get_market_summary(df_all, cur, mult)
    with st.expander("📊 Dữ liệu thị trường đang dùng làm context", expanded=False):
        st.code(market_ctx, language="text")

    st.markdown("---")

    # ── Gợi ý câu hỏi ────────────────────────────────────────────────────────
    st.markdown("**💡 Câu hỏi gợi ý — nhấn để hỏi ngay:**")
    cols = st.columns(len(SAMPLE_QUESTIONS))
    for i, q in enumerate(SAMPLE_QUESTIONS):
        if cols[i].button(q, key=f"sq_{i}", use_container_width=True):
            st.session_state["genbi_pending"] = q

    st.markdown("---")

    # ── Chat interface ────────────────────────────────────────────────────────
    if "genbi_messages" not in st.session_state:
        st.session_state["genbi_messages"] = []

    # Hiển thị lịch sử — AI dùng ai.png làm avatar
    for msg in st.session_state["genbi_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    pending    = st.session_state.pop("genbi_pending", None)
    user_input = st.chat_input("Hỏi về thị trường nông sản Việt Nam...")
    prompt     = pending or user_input

    if prompt:
        st.session_state["genbi_messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Đang phân tích..."):
                answer = call_groq(prompt, market_ctx,
                                   st.session_state["genbi_messages"][:-1])
            st.markdown(answer)

        st.session_state["genbi_messages"].append({"role": "assistant", "content": answer})

    # ── Nút xóa chat ──────────────────────────────────────────────────────────
    if st.session_state["genbi_messages"]:
        if st.button("Xóa lịch sử chat", key="clear_chat"):
            st.session_state["genbi_messages"] = []
            st.rerun()
