from ml.arima_baseline import main as arima_main
from ml.lstm_forecast import main as lstm_main

def main():
    print("Training ARIMA...")
    arima_main()

    print("Training LSTM...")
    lstm_main()

if __name__ == "__main__":
    main()