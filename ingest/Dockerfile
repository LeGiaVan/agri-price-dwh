FROM python:3.11-slim

WORKDIR /app
COPY ingest/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create logs dir
RUN mkdir -p /app/logs

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["python", "ingest/worldbank_ingest.py"]
