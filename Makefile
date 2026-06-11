.PHONY: init-db run-dashboard run-dbt ingest

init-db:
	python scripts/db_init.py

run-dashboard:
	docker compose up dashboard

run-dbt:
	docker compose run --rm dbt

ingest:
	docker compose run --rm ingest

start-all:
	docker compose up -d
