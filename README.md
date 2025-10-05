dbase-to-api (Docker + FastAPI + PostgreSQL)

Modernize dBASE/FoxPro `.dbf` files by importing to PostgreSQL and exposing a FastAPI REST API.

Quick start
1) Copy `.env.example` to `.env`.
2) Put `.dbf` files into `./data/`.
3) Run: `docker compose up --build`.

Services
- db: Postgres 16 (internal-only; connect via docker exec)
- importer: reads `.dbf` from `/data` and loads into Postgres
- api: FastAPI at http://localhost:8000

Reset database
- Remove the `pgdata` volume: `docker volume rm dbase-to-api_pgdata` (name may vary)

Connect to Postgres inside the container
```bash
docker exec -it dbase_pg psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

## Fetch public sample `.dbf` files

This repo includes a helper script that downloads small public datasets (Natural Earth shapefiles) and extracts their `.dbf` attribute tables into `./data/`.

```bash
python3 scripts/fetch_public_dbf.py
```

After running, you should see `.dbf` files in `./data/`. Then start the stack:

```bash
docker compose up --build
```

## Make a tiny local sample `.dbf`

If you prefer not to download anything, you can generate a 3-row `.dbf` using the containerized tools service:

```bash
docker compose run --rm tools python scripts/make_sample_dbf.py
```

This writes `data/sample_people.dbf`. Then run the importer:

```bash
docker compose up --build importer
```

## Testing

Run unit tests (no services needed):

```bash
pytest -q
```

This includes importer unit tests for type mapping and table inference.

Run integration tests (requires Docker):

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt

# Generate sample DBF and bring services up
docker-compose run --rm tools python scripts/make_sample_dbf.py
docker-compose up -d db
docker-compose run --rm importer
docker-compose up -d api

# Run integration tests locally (host Python)
PYTHONPATH=$(pwd) pytest -q -m integration
```

What it does:
- Generates a small `.dbf` locally
- Brings up the `db` container
- Runs the importer one-off
- Asserts rows exist using `psql` inside the container

## Exporting the database

After importing `.dbf` files, you can export the PostgreSQL database:

```bash
# SQL dump (schema + data)
make export-sql

# Custom format (use pg_restore later)
make export-custom
```

Outputs go to `exports/` (ignored by git).

