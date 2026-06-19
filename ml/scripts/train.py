import os
import duckdb
import pandas as pd
import numpy as np
import pickle
import torch
import torch.nn as nn
from sklearn.preprocessing import MinMaxScaler
from dotenv import load_dotenv

load_dotenv()

# --- Config ---
SEQ_LEN = 30
EPOCHS = 150
LR = 0.005
HIDDEN_SIZE = 64
NUM_LAYERS = 2
DROPOUT = 0.2
COMMODITIES = ['rice', 'coffee', 'pepper', 'cashew', 'rubber', 'cocoa', 'cotton']

# --- LSTM Model ---
class PriceLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, output_size, dropout):
        super(PriceLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout if num_layers > 1 else 0)
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        out, _ = self.lstm(x, (h0, c0))
        out = self.fc(out[:, -1, :])
        return out

def create_sequences(data, seq_length):
    xs = []
    ys = []
    for i in range(len(data) - seq_length):
        x = data[i:(i + seq_length)]
        y = data[i + seq_length][0] # Target is price at index 0
        xs.append(x)
        ys.append(y)
    return np.array(xs), np.array(ys)

def train_model(commodity, df):
    print(f"--- Training LSTM for {commodity} ---")
    
    # Feature Selection: Use price, lag1, lag7, 30d_avg, volatility
    features = ['price_usd_per_kg', 'price_lag_1', 'price_lag_7', 'price_30d_avg', 'price_30d_volatility']
    # Fill NAs
    df = df.sort_values('price_date')
    df = df[features].bfill().ffill()
    
    scaler = MinMaxScaler()
    scaled_data = scaler.fit_transform(df)
    
    X, y = create_sequences(scaled_data, SEQ_LEN)
    
    # Train test split (80-20)
    split = int(len(X) * 0.8)
    X_train, y_train = X[:split], y[:split]
    X_test, y_test = X[split:], y[split:]
    
    X_train_t = torch.tensor(X_train, dtype=torch.float32)
    y_train_t = torch.tensor(y_train, dtype=torch.float32).unsqueeze(1)
    X_test_t = torch.tensor(X_test, dtype=torch.float32)
    y_test_t = torch.tensor(y_test, dtype=torch.float32).unsqueeze(1)
    
    model = PriceLSTM(input_size=len(features), hidden_size=HIDDEN_SIZE, num_layers=NUM_LAYERS, output_size=1, dropout=DROPOUT)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    
    for epoch in range(EPOCHS):
        model.train()
        optimizer.zero_grad()
        out = model(X_train_t)
        loss = criterion(out, y_train_t)
        loss.backward()
        optimizer.step()
        
        if (epoch+1) % 50 == 0:
            model.eval()
            with torch.no_grad():
                val_out = model(X_test_t)
                val_loss = criterion(val_out, y_test_t)
            print(f"Epoch {epoch+1}/{EPOCHS}, Loss: {loss.item():.4f}, Val Loss: {val_loss.item():.4f}")
            
    # Calculate Test MAPE
    model.eval()
    with torch.no_grad():
        preds = model(X_test_t).numpy()
        
    # Inverse transform logic
    preds_padded = np.zeros((len(preds), len(features)))
    preds_padded[:, 0] = preds[:, 0]
    preds_inv = scaler.inverse_transform(preds_padded)[:, 0]
    
    actual_padded = np.zeros((len(y_test), len(features)))
    actual_padded[:, 0] = y_test
    actual_inv = scaler.inverse_transform(actual_padded)[:, 0]
    
    mape = np.mean(np.abs((actual_inv - preds_inv) / actual_inv)) * 100
    print(f"[{commodity}] Final Test MAPE: {mape:.2f}%")
    
    # Save Model & Scaler
    os.makedirs("ml/models", exist_ok=True)
    torch.save(model.state_dict(), f"ml/models/lstm_{commodity}.pt")
    with open(f"ml/models/scaler_{commodity}.pkl", "wb") as f:
        pickle.dump(scaler, f)
    print(f"Saved model to ml/models/lstm_{commodity}.pt")

def main():
    token = os.getenv("MOTHERDUCK_TOKEN")
    con = duckdb.connect(f"md:agri_dwh?motherduck_token={token}")
    
    print("Fetching gold_ml_features...")
    df_all = con.execute("SELECT * FROM gold.gold_ml_features").df()
    
    for comm in COMMODITIES:
        df_c = df_all[df_all['commodity'] == comm].copy()
        if len(df_c) > SEQ_LEN + 10:
            train_model(comm, df_c)
        else:
            print(f"Not enough data for {comm}. Skipping.")
            
    con.close()

if __name__ == "__main__":
    main()
