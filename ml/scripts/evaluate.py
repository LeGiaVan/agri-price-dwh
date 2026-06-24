"""
evaluate.py — Đánh giá chất lượng các LSTM model đã train
=============================================================
Chạy: python ml/scripts/evaluate.py

Output:
  - In bảng kết quả MSE / RMSE / MAE / MAPE ra stdout
  - Lưu file: ml/models/evaluation_results.json
  - (Tùy chọn) Vẽ biểu đồ Actual vs Predicted cho từng commodity

Yêu cầu:
  - Đã chạy train.py → các file ml/models/lstm_*.pt và scaler_*.pkl phải tồn tại
  - Biến môi trường MOTHERDUCK_TOKEN đã set (hoặc file .env ở root)
"""

import os
import sys
import json
import pickle
import logging
import numpy as np
import pandas as pd
import torch
import duckdb
from dotenv import load_dotenv

# ── Import dùng chung từ train.py ──────────────────────────────────────────────
# Thêm thư mục scripts vào path để import được train.py
sys.path.insert(0, os.path.dirname(__file__))
from train import PriceLSTM, create_sequences, SEQ_LEN, HIDDEN_SIZE, NUM_LAYERS, DROPOUT

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
COMMODITIES = ['cocoa', 'coffee', 'cotton', 'rice']   # 4 mặt hàng chính thức
FEATURES    = ['price_usd_per_kg', 'price_lag_1', 'price_lag_7',
               'price_30d_avg', 'price_30d_volatility']
TEST_RATIO  = 0.20                                     # 20% cuối làm test set
MODEL_DIR   = os.path.join(os.path.dirname(__file__), '..', 'models')
OUTPUT_JSON = os.path.join(MODEL_DIR, 'evaluation_results.json')

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
LOG = logging.getLogger('evaluate')

# ─────────────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────────────
def mse(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Mean Squared Error — đơn vị: (USD/kg)²"""
    return float(np.mean((actual - predicted) ** 2))

def rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Root Mean Squared Error — đơn vị: USD/kg"""
    return float(np.sqrt(mse(actual, predicted)))

def mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Mean Absolute Error — đơn vị: USD/kg"""
    return float(np.mean(np.abs(actual - predicted)))

def mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Mean Absolute Percentage Error — đơn vị: %
    Bỏ qua các điểm có actual = 0 để tránh chia 0.
    """
    mask = actual != 0
    if not mask.any():
        return float('nan')
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)

# ─────────────────────────────────────────────────────────────────────────────
# Đánh giá 1 commodity
# ─────────────────────────────────────────────────────────────────────────────
def evaluate_commodity(commodity: str, df: pd.DataFrame) -> dict | None:
    """
    Tái tạo lại test set giống hệt train.py (80/20 chronological),
    load model đã lưu, dự đoán và tính metrics.

    Returns dict với keys: commodity, n_train, n_test, mse, rmse, mae, mape,
                           date_range_test, min_price, max_price
    hoặc None nếu model không tồn tại / dữ liệu không đủ.
    """
    model_path  = os.path.join(MODEL_DIR, f'lstm_{commodity}.pt')
    scaler_path = os.path.join(MODEL_DIR, f'scaler_{commodity}.pkl')

    # Kiểm tra file tồn tại
    if not os.path.exists(model_path):
        LOG.warning(f'[{commodity}] Model không tìm thấy: {model_path}')
        return None
    if not os.path.exists(scaler_path):
        LOG.warning(f'[{commodity}] Scaler không tìm thấy: {scaler_path}')
        return None

    # Chuẩn bị data — giống hệt bước tiền xử lý trong train.py
    df = df.sort_values('price_date').reset_index(drop=True)
    date_col = df['price_date'].copy()  # giữ lại để hiển thị
    df_feat = df[FEATURES].bfill().ffill()

    # Kiểm tra đủ dữ liệu
    if len(df_feat) <= SEQ_LEN + 10:
        LOG.warning(f'[{commodity}] Không đủ dữ liệu ({len(df_feat)} rows). Bỏ qua.')
        return None

    # Load scaler
    with open(scaler_path, 'rb') as f:
        scaler = pickle.load(f)

    # Scale
    scaled_data = scaler.transform(df_feat.values)

    # Tạo sequences
    X, y = create_sequences(scaled_data, SEQ_LEN)

    # Split 80/20 chronological — PHẢI giống hệt train.py
    split   = int(len(X) * (1 - TEST_RATIO))
    X_test  = X[split:]
    y_test  = y[split:]

    if len(X_test) == 0:
        LOG.warning(f'[{commodity}] Test set rỗng sau split. Bỏ qua.')
        return None

    # Load model
    model = PriceLSTM(
        input_size  = len(FEATURES),
        hidden_size = HIDDEN_SIZE,
        num_layers  = NUM_LAYERS,
        output_size = 1,
        dropout     = DROPOUT,
    )
    model.load_state_dict(torch.load(model_path, map_location='cpu'))
    model.eval()

    # Dự đoán trên test set
    X_test_t = torch.tensor(X_test, dtype=torch.float32)
    with torch.no_grad():
        preds_scaled = model(X_test_t).numpy()  # shape: [N, 1]

    # Inverse transform: pad về đúng shape [N, n_features]
    n = len(preds_scaled)

    preds_padded  = np.zeros((n, len(FEATURES)))
    preds_padded[:, 0] = preds_scaled[:, 0]
    preds_inv = scaler.inverse_transform(preds_padded)[:, 0]

    actual_padded = np.zeros((n, len(FEATURES)))
    actual_padded[:, 0] = y_test
    actual_inv = scaler.inverse_transform(actual_padded)[:, 0]

    # Tính metrics
    _mse  = mse(actual_inv, preds_inv)
    _rmse = rmse(actual_inv, preds_inv)
    _mae  = mae(actual_inv, preds_inv)
    _mape = mape(actual_inv, preds_inv)

    # Thông tin thêm
    test_dates    = date_col.iloc[split + SEQ_LEN : split + SEQ_LEN + n]
    date_range    = f"{test_dates.min()} → {test_dates.max()}" if len(test_dates) > 0 else 'N/A'

    result = {
        'commodity'     : commodity,
        'n_train'       : split,
        'n_test'        : n,
        'date_range_test': date_range,
        'mse'           : round(_mse,  6),
        'rmse'          : round(_rmse, 6),
        'mae'           : round(_mae,  6),
        'mape_pct'      : round(_mape, 2),
        'actual_mean'   : round(float(actual_inv.mean()), 4),
        'pred_mean'     : round(float(preds_inv.mean()),  4),
        'actual_min'    : round(float(actual_inv.min()),  4),
        'actual_max'    : round(float(actual_inv.max()),  4),
        # Lưu để vẽ biểu đồ nếu cần
        '_actual'       : actual_inv.tolist(),
        '_predicted'    : preds_inv.tolist(),
        '_test_dates'   : test_dates.astype(str).tolist(),
    }

    LOG.info(
        f'[{commodity}] MSE={_mse:.6f}  RMSE={_rmse:.4f}  '
        f'MAE={_mae:.4f}  MAPE={_mape:.2f}%  '
        f'(test={n} samples, {date_range})'
    )
    return result

# ─────────────────────────────────────────────────────────────────────────────
# Print bảng kết quả
# ─────────────────────────────────────────────────────────────────────────────
def print_results_table(results: list[dict]) -> None:
    """In bảng kết quả ra stdout theo dạng Markdown."""
    if not results:
        print('\nKhông có kết quả nào để hiển thị.\n')
        return

    header = (
        f"\n{'='*80}\n"
        f"  KẾT QUẢ ĐÁNH GIÁ LSTM — {len(results)} MẶT HÀNG\n"
        f"{'='*80}\n"
    )
    print(header)

    # Header bảng
    print(f"{'Commodity':<10} {'N-Test':>7} {'MSE':>12} {'RMSE':>10} {'MAE':>10} {'MAPE%':>8}  {'Nhận xét'}")
    print('-' * 80)

    for r in results:
        mape_val = r['mape_pct']
        if   mape_val < 5:   note = '🟢 Xuất sắc'
        elif mape_val < 10:  note = '🟡 Tốt'
        elif mape_val < 20:  note = '🟠 Khá'
        else:                note = '🔴 Kém'

        print(
            f"{r['commodity']:<10} "
            f"{r['n_test']:>7} "
            f"{r['mse']:>12.6f} "
            f"{r['rmse']:>10.4f} "
            f"{r['mae']:>10.4f} "
            f"{mape_val:>7.2f}%  "
            f"{note}"
        )

    print('-' * 80)
    avg_mape = np.mean([r['mape_pct'] for r in results])
    avg_rmse = np.mean([r['rmse']     for r in results])
    print(f"{'TRUNG BÌNH':<10} {'':>7} {'':>12} {avg_rmse:>10.4f} {'':>10} {avg_mape:>7.2f}%")
    print(f"\n📁 Kết quả chi tiết lưu tại: {os.path.abspath(OUTPUT_JSON)}\n")

    # Phụ lục: date range của test set
    print("📅 Khoảng thời gian test set:")
    for r in results:
        print(f"   {r['commodity']:<8}: {r['date_range_test']}")
    print()

# ─────────────────────────────────────────────────────────────────────────────
# (Tùy chọn) Vẽ biểu đồ Actual vs Predicted
# ─────────────────────────────────────────────────────────────────────────────
def plot_results(results: list[dict]) -> None:
    """Vẽ biểu đồ Actual vs Predicted cho từng commodity.
    Chỉ chạy nếu matplotlib đã được cài.
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        LOG.info('matplotlib chưa được cài. Bỏ qua vẽ biểu đồ.')
        return

    n_plots = len(results)
    if n_plots == 0:
        return

    fig, axes = plt.subplots(n_plots, 1, figsize=(14, 4 * n_plots), sharex=False)
    if n_plots == 1:
        axes = [axes]

    fig.suptitle('LSTM Model — Actual vs Predicted (Test Set)', fontsize=14, fontweight='bold')

    COLORS = {
        'cocoa' : '#7C4A2D',
        'coffee': '#8B5E3C',
        'cotton': '#4B7F9F',
        'rice'  : '#306D29',
    }

    for ax, r in zip(axes, results):
        dates     = pd.to_datetime(r['_test_dates'])
        actual    = np.array(r['_actual'])
        predicted = np.array(r['_predicted'])
        color     = COLORS.get(r['commodity'], '#555')

        ax.plot(dates, actual,    color=color,   linewidth=2,   label='Actual',    alpha=0.9)
        ax.plot(dates, predicted, color='#f59e0b', linewidth=1.8, label='Predicted', linestyle='--', alpha=0.85)
        ax.fill_between(dates, actual, predicted, alpha=0.1, color=color)

        ax.set_title(
            f"{r['commodity'].upper()}  —  "
            f"RMSE={r['rmse']:.4f}  MAE={r['mae']:.4f}  MAPE={r['mape_pct']:.2f}%",
            fontsize=11,
        )
        ax.set_ylabel('USD / kg')
        ax.legend(loc='upper left', fontsize=9)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%Y'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        ax.grid(True, alpha=0.3)
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha='right')

    plt.tight_layout()

    plot_path = os.path.join(MODEL_DIR, 'evaluation_plot.png')
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    LOG.info(f'Đã lưu biểu đồ: {plot_path}')
    plt.show()

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    LOG.info('Bắt đầu đánh giá LSTM models...')

    # Kết nối MotherDuck
    token = os.getenv('MOTHERDUCK_TOKEN')
    if not token:
        LOG.error('Không tìm thấy MOTHERDUCK_TOKEN trong biến môi trường / .env')
        sys.exit(1)

    try:
        con = duckdb.connect(f'md:agri_dwh?motherduck_token={token}')
        LOG.info('Kết nối MotherDuck thành công.')
        df_all = con.execute('SELECT * FROM gold.gold_ml_features').df()
        con.close()
        LOG.info(f'Tải được {len(df_all):,} rows từ gold.gold_ml_features.')
    except Exception as e:
        LOG.error(f'Lỗi kết nối MotherDuck: {e}')
        sys.exit(1)

    # Đánh giá từng commodity
    results = []
    for comm in COMMODITIES:
        LOG.info(f'--- Đánh giá: {comm} ---')
        df_c = df_all[df_all['commodity'] == comm].copy()
        result = evaluate_commodity(comm, df_c)
        if result:
            results.append(result)

    # In bảng
    print_results_table(results)

    # Lưu JSON (bỏ _actual/_predicted để file gọn)
    os.makedirs(MODEL_DIR, exist_ok=True)
    export = []
    for r in results:
        e = {k: v for k, v in r.items() if not k.startswith('_')}
        export.append(e)

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(export, f, ensure_ascii=False, indent=2)
    LOG.info(f'Đã lưu JSON: {OUTPUT_JSON}')

    # Vẽ biểu đồ (nếu matplotlib có)
    plot_results(results)

    LOG.info('Hoàn thành đánh giá.')


if __name__ == '__main__':
    main()
