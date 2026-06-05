FROM python:3.11-slim

LABEL maintainer="agri-price-dwh team"
LABEL description="ML forecasting jobs for agri-price-dwh"

RUN apt-get update && apt-get install -y \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ml/requirements.txt /tmp/ml-requirements.txt
RUN pip install --no-cache-dir -r /tmp/ml-requirements.txt

COPY ml /app/ml

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["python", "ml/arima_baseline.py"]
