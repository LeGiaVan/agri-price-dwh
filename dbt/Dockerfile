FROM python:3.11-slim

WORKDIR /app
COPY dbt/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["dbt", "build", "--profiles-dir", "."]
