.PHONY: sample up-db import up-api test-unit test-integration down clean logs all test

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
	@docker compose run -e PYTHONPATH=/workspace --rm tools pytest -q -m "not integration"

# Integration tests run on the host so they can call docker-compose inside tests
test-integration: up-db sample import up-api
	@docker compose run --rm tester

logs:
	@docker compose logs -f db importer api

down:
	@docker compose down

clean:
	@docker compose down -v

all: test-unit test-integration

test: test-unit test-integration

