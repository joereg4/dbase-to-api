# Contributing

Thanks for your interest in contributing!

## Getting started

1. Fork and clone the repo.
2. Copy `.env.example` to `.env`.
3. Run the one-command demo to verify your environment:
   ```bash
   make demo-public
   ```
4. Run all tests:
   ```bash
   make test
   ```

## Development loops

- Import your own `.dbf` files by placing them in `data/` and running:
  ```bash
  docker compose run --rm importer
  docker compose up -d api
  ```
- Browse the dynamic API at `http://localhost:8000/docs`.

## Pull requests

- Create a feature branch.
- Include tests for any new logic.
- Ensure `make test` passes locally.
- Keep changes focused; avoid unrelated refactors.

## Code style

- Python 3.12
- FastAPI + SQLAlchemy
- Prefer readable names; avoid unnecessary complexity.

## Running tests

Tests run against PostgreSQL. `make test-unit` starts the database and fails if it is unreachable.

- Unit tests:
  ```bash
  make test-unit
  ```
- All tests (unit + integration) run in Docker via the `tester` service:
  ```bash
  make test
  ```
- Integration tests only:
  ```bash
  make test-integration
  ```

**Caveats:**
- The `tester` service mounts `/var/run/docker.sock` so integration tests can run nested compose commands. Do not use this on untrusted hosts.
- `make test` and `make test-integration` delete `data/*.dbf` before generating a sample. Copy those files aside if you need to keep them. The tests leave PostgreSQL running.

## Exporting data

- After importing, you can export the database:
  ```bash
  make export-sql
  make export-custom
  ```

## Reporting issues

- Use GitHub Issues. Please include steps to reproduce and environment details.
