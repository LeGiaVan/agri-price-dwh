@echo off
if "%1"=="init-db" goto init-db
if "%1"=="ingest-wb" goto ingest-wb
if "%1"=="run-dashboard" goto run-dashboard
if "%1"=="run-dbt" goto run-dbt
if "%1"=="ingest" goto ingest
if "%1"=="start-all" goto start-all

echo Usage: run.bat [init-db^|ingest-wb^|run-dashboard^|run-dbt^|ingest^|start-all]
goto :eof

:init-db
python scripts/db_init.py
goto :eof

:ingest-wb
docker compose run --rm ingest python /app/ingest/worldbank_ingest.py
goto :eof

:run-dashboard
docker compose up dashboard
goto :eof

:run-dbt
docker compose run --rm dbt
goto :eof

:ingest
docker compose run --rm ingest
goto :eof

:start-all
docker compose up -d
goto :eof
