# Model Evaluation

Metrics are calculated on the time-based holdout split.

| model   | commodity   |       rmse |        mae |     mape | extra                                         |
|:--------|:------------|-----------:|-----------:|---------:|:----------------------------------------------|
| ARIMA   | rice        | 71.4466    | 54.3279    | 16.8047  | order=(1, 1, 0);adf_pvalue=0.3435087488253673 |
| Naive   | rice        | 51.1429    | 28.7613    |  8.68043 | price_lag_1                                   |
| ARIMA   | coffee      |  1.68128   |  1.43212   | 36.3738  | order=(1, 1, 0);adf_pvalue=0.5032040795282507 |
| Naive   | coffee      |  0.380473  |  0.278812  |  7.57555 | price_lag_1                                   |
| ARIMA   | rubber      |  0.167196  |  0.150805  |  9.56068 | order=(2, 1, 2);adf_pvalue=0.2336872766142969 |
| Naive   | rubber      |  0.0787739 |  0.0576894 |  3.55811 | price_lag_1                                   |
