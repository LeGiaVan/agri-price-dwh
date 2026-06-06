.PHONY: init-db run-dashboard run-dbt ingest

init-db:
	python scripts/db_init.py

seed-bronze:
	docker compose run --rm fao_bronze_seed

run-dashboard:
	docker compose up dashboard

run-dbt:
	docker compose run --rm dbt

ingest:
	docker compose run --rm ingest

start-all:
	docker compose up -d
