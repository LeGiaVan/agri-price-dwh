FROM python:3.11-slim

LABEL maintainer="agri-price-dwh team"
LABEL description="Data Lakehouse - Phan tich & Du bao Gia Nong san Viet Nam"

# System deps
RUN apt-get update && apt-get install -y \
    git curl build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create log dir
RUN mkdir -p /app/logs

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["python", "ingest/fao_ingest.py"]