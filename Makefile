.PHONY: sample up-db import up-api test-unit test-integration down clean logs all test export-sql export-custom exports-dir demo-public format format-check

.DEFAULT_GOAL := test

SHELL := /bin/bash

sample:
	@docker compose run --rm tools python scripts/make_sample_dbf.py

up-db:
	@docker compose up -d db

import: up-db sample
	@docker compose run --rm importer

up-api: up-db
	@docker compose up -d api

test-unit:
	@docker compose run -e PYTHONPATH=/workspace --rm tools pytest -q

# Integration tests run on the host so they can call docker-compose inside tests
test-integration: up-db sample import up-api
	@docker compose run --rm tester

logs:
	@docker compose logs -f db importer api

down:
	@docker compose down

clean:
	@docker compose down -v

all: test

test: up-db sample import up-api
	@docker compose run --rm tester

exports-dir:
	@mkdir -p exports

export-sql: exports-dir
	@docker exec -i dbase_pg pg_dump -U "$$(grep ^POSTGRES_USER .env | cut -d= -f2)" -d "$$(grep ^POSTGRES_DB .env | cut -d= -f2)" -h localhost -p 5432 --no-owner --no-privileges > exports/schema_data.sql || true
	@echo "Wrote exports/schema_data.sql (if pg_dump is accessible via exec)"

export-custom: exports-dir
	@docker exec -i dbase_pg pg_dump -U "$$(grep ^POSTGRES_USER .env | cut -d= -f2)" -d "$$(grep ^POSTGRES_DB .env | cut -d= -f2)" -h localhost -p 5432 -Fc > exports/database.dump || true
	@echo "Wrote exports/database.dump (custom format)"

demo-public: up-db
	@docker compose run --rm tools python scripts/fetch_public_dbf.py
	@docker compose run --rm importer
	@docker compose up -d api
	@echo "\nDemo ready:"
	@echo "- Health: http://localhost:8000/health"
	@echo "- Docs:   http://localhost:8000/docs"
	@echo "- Tables: http://localhost:8000/db/tables\n"

format:
	@docker compose run --rm tools black .

format-check:
	@docker compose run --rm tools black --check .

