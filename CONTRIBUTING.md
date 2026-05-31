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

- Unit tests only (no live stack required):
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
- `make test-integration` may run `docker compose down` and remove `data/*.dbf` during teardown. Stop local stacks first or use a clean clone if you need to preserve running services or sample data.

## Exporting data

- After importing, you can export the database:
  ```bash
  make export-sql
  make export-custom
  ```

## Reporting issues

- Use GitHub Issues. Please include steps to reproduce and environment details.
