# Model Evaluation

Metrics are calculated on the time-based holdout split.

| model   | commodity   |      rmse |       mae |     mape | extra                                          |
|:--------|:------------|----------:|----------:|---------:|:-----------------------------------------------|
| ARIMA   | rice        | 71.4466   | 54.3279   | 16.8047  | order=(1, 1, 0);adf_pvalue=0.34350874882536747 |
| Naive   | rice        | 51.1429   | 28.7613   |  8.68043 | price_lag_1                                    |
| ARIMA   | coffee      |  1.68128  |  1.43212  | 36.3738  | order=(1, 1, 0);adf_pvalue=0.5032040795282506  |
| Naive   | coffee      |  0.380473 |  0.278812 |  7.57555 | price_lag_1                                    |
| ARIMA   | pepper      |  0.614547 |  0.520723 | 11.4615  | order=(0, 1, 0);adf_pvalue=0.3493721346656067  |
| Naive   | pepper      |  0.228979 |  0.172056 |  3.95959 | price_lag_1                                    |
