dbase-to-api (Docker + FastAPI + PostgreSQL)

[![CI](https://github.com/joereg4/dbase-to-api/actions/workflows/ci.yml/badge.svg)](https://github.com/joereg4/dbase-to-api/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Modernize dBASE/FoxPro `.dbf` files by importing to PostgreSQL and exposing a FastAPI REST API.

Quick start
1) Copy `.env.example` to `.env`.
2) One-command demo with public data: `make demo-public`
   - Health: http://localhost:8000/health
   - Docs:   http://localhost:8000/docs
   - Tables: http://localhost:8000/db/tables
3) Or bring your own `.dbf`: put files into `./data/` then run:
   - `docker compose run --rm importer`
   - `docker compose up -d api`

Services
- db: Postgres 16 (internal-only; connect via docker exec)
- importer: reads `.dbf` from `/data` and loads into Postgres
- api: FastAPI at http://localhost:8000
 
Contributing
- See `CONTRIBUTING.md`. Code of conduct: `CODE_OF_CONDUCT.md`.
 
CI (GitHub Actions)
- On each push/PR, CI builds images, checks code formatting with Black, and runs all tests in Docker.
- Common failure reasons:
  - Formatting: run `make format` locally to auto-fix; CI uses `black --check .`.
  - Missing env file in forks: ensure `.env.example` stays updated; CI copies it to `.env`.
  - Docker Desktop file sharing (macOS dev only): follow the "Mac users" section if running tests locally.
 
Formatting (Black)
- The project pins Black in `scripts/requirements.txt`. Always run Black via the tools container to match CI exactly:
  - Auto-format: `make format`
  - Check only:  `make format-check`

Requirements
- Docker Desktop (or Docker Engine) with Compose v2
- macOS, Linux, or Windows with WSL2
- Internet access for public demo data

Security notes
- Dependencies are pinned. We periodically bump FastAPI/Starlette to include upstream security fixes. Current FastAPI `0.117.0` pulls Starlette `0.48.x`, which addresses recent Starlette CVEs.
- Base images are `python:3.12-slim` (Debian). Dockerfiles install the latest `openssl` and `ca-certificates` from Debian security repos during build.
- To refresh security fixes force-rebuild images:

```bash
docker compose build --no-cache api importer
make test
```

Architecture
- Source `.dbf` files in `data/`
- Importer reads each `.dbf` and creates a PostgreSQL table (one table per file)
- FastAPI provides dynamic endpoints to list tables, columns, and rows

Minimal API examples
```bash
curl http://localhost:8000/db/tables
curl http://localhost:8000/db/tables/your_table/columns
curl "http://localhost:8000/db/tables/your_table/rows?limit=10&offset=0"
```

Table naming and schema inference
- Table names come from the `.dbf` basename (non-alphanumeric chars may be normalized)
- Strings map to `TEXT`, numbers to `NUMERIC(precision, scale)` or `INTEGER` when safe
- Dates map to `DATE`, datetimes to `TIMESTAMP` (if present)
- Column names are lowercased; collisions are disambiguated

Performance notes
- Large imports: prefer running importer once, then start API
- Index after import if you need fast filtering/sorting
- Limit/offset are bounded to protect API; adjust in code if needed

Troubleshooting
- Port 8000 in use: stop the other service or change the published port
- "mounts denied" on macOS: ensure your repo path is shared in Docker Desktop → Settings → Resources → File sharing
- Public data fetch 406: use `make demo-public` (uses NACIS CDN) or add your own `.dbf` to `data/`
- CI failures:
  - Formatting: run `make format`
  - Missing `.env`: kept in `.env.example` and copied in CI; ensure it's present
  - Workspace mount: CI sets an absolute mount; open an issue if it regresses


Reset database
- Remove the `pgdata` volume: `docker volume rm dbase-to-api_pgdata` (name may vary)

Connect to Postgres inside the container
```bash
docker exec -it dbase_pg psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

## Fetch public sample `.dbf` files

This repo includes a helper script that downloads small public datasets (Natural Earth shapefiles) and extracts their `.dbf` attribute tables into `./data/`.

```bash
docker compose run --rm tools python scripts/fetch_public_dbf.py
```

After running, you should see `.dbf` files in `./data/`. Then start the stack:

```bash
docker compose up -d api
```

## Make a tiny local sample `.dbf`

If you prefer not to download anything, you can generate a 3-row `.dbf` using the containerized tools service:

```bash
docker compose run --rm tools python scripts/make_sample_dbf.py
```

This writes `data/sample_people.dbf`. Then run the importer:

```bash
docker compose run --rm importer
```

## Testing

Run all tests (unit + integration) in Docker:

```bash
make test
```

Notes:
- Integration tests run in the `tester` container and call Docker from inside; ensure Docker Desktop file sharing is configured (see below).

Mac users: enable Docker Desktop file sharing

If you want to run integration tests fully in containers (via the `tester` service) or invoke `docker compose` from inside a container, you must share your project path with Docker Desktop so the daemon can mount it.

Steps (macOS):
- Docker Desktop → Settings → Resources → File sharing
- Add your project path (for example: `/Users/youruser/dbase-to-api` or the parent folder `/Users/youruser`)
- Apply and restart Docker Desktop

After enabling file sharing, you can run:

```bash
docker compose run --rm tester
```

What integration tests do:
- Generate a sample `.dbf`
- Bring up `db` and start the API
- Run the importer one-off
- Exercise dynamic endpoints (tables/columns/rows)

## Import your own `.dbf` files

Bring any `.dbf` files you want to import and place them in the `data/` folder at the repo root (they will be mounted read-only into the importer container at `/data`). Then run:

```bash
# 1) Ensure Postgres is up
docker compose up -d db

# 2) Import every .dbf found in ./data
docker compose run --rm importer

# 3) Start the API
docker compose up -d api

# 4) Browse
open http://localhost:8000/db/tables
```

Notes:
- You can mix multiple `.dbf` files; each becomes a table in PostgreSQL with the `.dbf` basename as the table name.
- If you add or change files in `data/`, re-run the importer step.
- Exports are available after import via `make export-sql` or `make export-custom` (see Exporting section).
 - Reset database: remove the `pgdata` volume to clear data, e.g. `docker volume rm dbase-to-api_pgdata` (name may vary).

## Exporting the database

After importing `.dbf` files, you can export the PostgreSQL database:

```bash
# SQL dump (schema + data)
make export-sql

# Custom format (use pg_restore later)
make export-custom
```

Outputs go to `exports/` (ignored by git).

