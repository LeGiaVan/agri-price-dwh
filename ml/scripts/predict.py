import os
import duckdb
import pandas as pd
import numpy as np
import pickle
import torch
from train import PriceLSTM, SEQ_LEN, HIDDEN_SIZE, NUM_LAYERS, DROPOUT, COMMODITIES
from dotenv import load_dotenv

load_dotenv()

# Forecast horizon (months/days)
FORECAST_STEPS = 6

def predict_future(commodity, df, model, scaler, features):
    # Get last SEQ_LEN days
    df = df.sort_values('price_date')
    last_data = df[features].bfill().ffill().tail(SEQ_LEN).values
    
    scaled_data = scaler.transform(last_data)
    curr_seq = torch.tensor(scaled_data, dtype=torch.float32).unsqueeze(0)
    
    predictions = []
    
    model.eval()
    with torch.no_grad():
        for _ in range(FORECAST_STEPS):
            pred = model(curr_seq).item()
            predictions.append(pred)
            
            # Autoregressive step: append prediction to sequence
            new_row = curr_seq[0, -1, :].clone()
            new_row[0] = pred # Update price feature
            # The other features (lags, etc) would ideally be updated properly, 
            # but for simple autoregression we keep them as last known or shift them
            
            new_row = new_row.unsqueeze(0).unsqueeze(0)
            curr_seq = torch.cat((curr_seq[:, 1:, :], new_row), dim=1)
            
    # Inverse transform
    preds_padded = np.zeros((FORECAST_STEPS, len(features)))
    preds_padded[:, 0] = predictions
    preds_inv = scaler.inverse_transform(preds_padded)[:, 0]
    
    return preds_inv

def main():
    token = os.getenv("MOTHERDUCK_TOKEN")
    con = duckdb.connect(f"md:agri_dwh?motherduck_token={token}")
    
    print("Fetching latest gold_ml_features...")
    df_all = con.execute("SELECT * FROM gold.gold_ml_features").df()
    
    forecasts = []
    
    for comm in COMMODITIES:
        model_path = f"ml/models/lstm_{comm}.pt"
        scaler_path = f"ml/models/scaler_{comm}.pkl"
        
        if not os.path.exists(model_path):
            print(f"Model for {comm} not found. Run train.py first.")
            continue
            
        df_c = df_all[df_all['commodity'] == comm].copy()
        if len(df_c) < SEQ_LEN:
            continue
            
        features = ['price_usd_per_kg', 'price_lag_1', 'price_lag_7', 'price_30d_avg', 'price_30d_volatility']
        
        # Load model & scaler
        model = PriceLSTM(len(features), HIDDEN_SIZE, NUM_LAYERS, 1, DROPOUT)
        model.load_state_dict(torch.load(model_path))
        
        with open(scaler_path, "rb") as f:
            scaler = pickle.load(f)
            
        # Predict
        last_date = pd.to_datetime(df_c['price_date'].max())
        preds = predict_future(comm, df_c, model, scaler, features)
        
        # Calculate confidence interval (heuristic: expanding bounds over time)
        for i, p in enumerate(preds):
            future_date = last_date + pd.Timedelta(days=30*(i+1)) # Assuming approx monthly steps for 6 steps
            ci_margin = p * (0.05 + 0.01 * i) # 5% base + 1% per step uncertainty
            
            forecasts.append({
                'forecast_date': future_date.date(),
                'commodity': comm,
                'predicted_price': p,
                'ci_lower': p - ci_margin,
                'ci_upper': p + ci_margin
            })
            
    if forecasts:
        df_fc = pd.DataFrame(forecasts)
        print("Upserting into gold.forecast_lstm...")
        
        # Clear old forecasts and insert new
        df_fc.to_csv("temp_forecast.csv", index=False)
        con.execute("DELETE FROM gold.forecast_lstm")
        con.execute("INSERT INTO gold.forecast_lstm SELECT forecast_date::DATE, commodity::VARCHAR, predicted_price::DOUBLE, ci_lower::DOUBLE, ci_upper::DOUBLE FROM read_csv_auto('temp_forecast.csv')")
        os.remove("temp_forecast.csv")
        print(f"Inserted {len(df_fc)} forecast records.")
    
    con.close()

if __name__ == "__main__":
    main()
