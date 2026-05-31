# dbase-to-api Repo Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Address the repo review findings in phased, shippable increments—fix doc/code drift and broken DX first, then importer/API hardening, then optional production and CI investments.

**Architecture:** Keep the existing Docker Compose layout (`db` → `importer` → `api`). Changes stay localized: importer owns `.dbf` → Postgres semantics; API owns health/readiness and HTTP surface; root `Makefile`/`README` own developer workflow. No new services in Phase 1–2.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL 16, Docker Compose, pytest, Black.

**Source:** Repo review (2026-05-31). This repo has **no** `src/puppeteer/` path—Docker builds use `docker compose build` from the repo root.

---

## File map (what changes where)

| Area | Create | Modify |
|------|--------|--------|
| Docs cleanup | — | Delete `api/app/README.md` |
| DX / Makefile | — | `Makefile` (`test-unit`, `export-*`) |
| README accuracy | — | `README.md` (naming, production callout, Docker build section) |
| Health + DB | `api/app/db.py` (optional thin helper) | `api/app/main.py`, `api/app/config.py` |
| Importer encoding | — | `importer/convert_dbase.py`, `.env.example` |
| Table naming (optional Phase 2) | `importer/naming.py` | `importer/convert_dbase.py`, tests |
| Fetch script | — | `scripts/fetch_public_dbf.py` |
| Dependencies | — | `api/requirements.txt`, `importer/requirements.txt` |
| Tests | `tests/test_health_db.py` | `tests/test_smoke.py`, importer tests if naming added |

---

## Phase 1 — Quick wins & high priority (ship first)

**Outcome:** Accurate docs, working `make test-unit`, honest health check, no stray duplicate README.

---

### Task 1: Remove duplicate `api/app/README.md`

**Files:**
- Delete: `api/app/README.md`

- [ ] **Step 1: Confirm file is a duplicate of root README**

Run: `diff README.md api/app/README.md || true`  
Expected: little or no diff (or wholly redundant content).

- [ ] **Step 2: Delete the file**

```bash
rm api/app/README.md
```

- [ ] **Step 3: Commit**

```bash
git add -u api/app/README.md
git commit -m "docs: remove duplicate README from api/app"
```

---

### Task 2: Fix `make test-unit` PYTHONPATH

**Files:**
- Modify: `Makefile:19-20`

- [ ] **Step 1: Update test-unit target**

Replace line 20 in `Makefile`:

```makefile
test-unit:
	@docker compose run -e PYTHONPATH=$$(pwd) --rm tools pytest -q
```

Rationale: `docker-compose.yml` mounts `${PWD}` and sets `working_dir: ${PWD}`; `/workspace` only works if the repo lives at that path.

- [ ] **Step 2: Verify unit tests run**

Run: `make test-unit`  
Expected: pytest collects and runs (may skip integration-only tests); exit code 0.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "fix: align test-unit PYTHONPATH with compose mount"
```

---

### Task 3: Align README with actual importer behavior

**Files:**
- Modify: `README.md` (lines 65–69 and add sections below)

- [ ] **Step 1: Replace inaccurate table-naming bullets**

In `README.md`, replace the "Table naming and schema inference" bullets with:

```markdown
Table naming and schema inference
- Table names are the `.dbf` basename lowercased (e.g. `Customers.DBF` → `customers`)
- Non-alphanumeric characters in basenames are **not** stripped; avoid odd filenames or rename files before import
- Strings map to `TEXT`, numbers to `NUMERIC(precision, scale)` or `INTEGER` when safe
- Dates map to `DATE`, datetimes to `TIMESTAMP` (if present)
- Column names are lowercased; **duplicate column names after lowercasing are not disambiguated** (fix the source `.dbf` or extend the importer)
- Default `.dbf` encoding is `latin-1` (override with `DBF_ENCODING` after Task 6)
```

- [ ] **Step 2: Add "Development vs production" callout**

Insert after the intro or before "Minimal API examples":

```markdown
## Development vs production

This project is optimized for **local migration and demos**:
- No API authentication or rate limiting
- Default Postgres credentials via `.env`
- Dynamic SQL routes are read-only but expose all imported tables

Do not expose the API to the public internet without a reverse proxy, auth, and a read-only database role.
```

- [ ] **Step 3: Add "Building images" section**

```markdown
## Building images

From the repository root (there is no `src/puppeteer/` Dockerfile in this repo):

```bash
docker compose build          # all services
docker compose build api      # API only
docker compose build importer # importer only
```
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: align README with importer behavior and Docker usage"
```

---

### Task 4: Deep health check (`/health` verifies Postgres)

**Files:**
- Create: `api/app/db.py`
- Modify: `api/app/main.py`
- Create: `tests/test_health_db.py`
- Modify: `tests/test_smoke.py` (if assertions change)

- [ ] **Step 1: Write failing test for DB-aware health**

Create `tests/test_health_db.py`:

```python
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def test_health_ok_when_db_responds():
    from api.app.main import app

    client = TestClient(app)
    with patch("api.app.db.check_database", return_value=True):
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_health_503_when_db_unavailable():
    from api.app.main import app

    client = TestClient(app)
    with patch("api.app.db.check_database", return_value=False):
        r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["status"] == "degraded"
    assert r.json()["database"] == "unavailable"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run -e PYTHONPATH=$$(pwd) --rm tools pytest tests/test_health_db.py -v`  
Expected: FAIL (module `api.app.db` or `check_database` missing).

- [ ] **Step 3: Implement `api/app/db.py`**

```python
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from .config import settings

log = logging.getLogger("api.db")
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def check_database() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        log.exception("database health check failed")
        return False
```

- [ ] **Step 4: Update `/health` in `api/app/main.py`**

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .db import check_database

# ... existing middleware ...

@app.get("/health")
def health():
    if check_database():
        return {"status": "ok", "database": "ok"}
    return JSONResponse(
        status_code=503,
        content={"status": "degraded", "database": "unavailable"},
    )
```

- [ ] **Step 5: Update `tests/test_smoke.py`**

Patch `check_database` to return `True` so smoke test does not require a live DB:

```python
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_health_endpoint_importable():
    from api.app.main import app

    client = TestClient(app)
    with patch("api.app.main.check_database", return_value=True):
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"
```

- [ ] **Step 6: Run tests**

Run: `make test-unit`  
Expected: PASS including `test_health_db.py` and `test_smoke.py`.

- [ ] **Step 7: Commit**

```bash
git add api/app/db.py api/app/main.py tests/test_health_db.py tests/test_smoke.py
git commit -m "feat: health endpoint verifies database connectivity"
```

---

### Task 5: Resolve unused `python-dotenv`

**Files:**
- Modify: `api/requirements.txt`, `importer/requirements.txt` **OR** `api/app/config.py`, `importer/convert_dbase.py`

**Decision:** Prefer **remove** unless you need host-side `python` without Docker (then load in `config.py` only).

- [ ] **Step 1: Confirm no imports**

Run: `rg 'dotenv|load_dotenv' --type py`  
Expected: no matches in application code.

- [ ] **Step 2a (recommended): Remove from requirements**

Remove `python-dotenv==...` lines from:
- `api/requirements.txt`
- `importer/requirements.txt`

Rebuild: `docker compose build api importer`

- [ ] **Step 2b (alternative): Use dotenv in API config**

In `api/app/config.py` at top:

```python
from dotenv import load_dotenv

load_dotenv()  # no-op in Docker when env_file is used; helps local pytest
```

Keep dependency only in `api/requirements.txt`.

- [ ] **Step 3: Run `make test-unit`**

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add api/requirements.txt importer/requirements.txt  # or config.py
git commit -m "chore: remove unused python-dotenv dependency"
```

---

### Task 6: `DBF_ENCODING` environment variable

**Files:**
- Modify: `importer/convert_dbase.py`, `.env.example`, `README.md`
- Test: extend `tests/test_importer_main.py` or add `tests/test_importer_encoding.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_importer_encoding.py`:

```python
import os
from unittest.mock import patch

import importer.convert_dbase as conv


def test_dbf_encoding_defaults_to_latin1():
    with patch.dict(os.environ, {}, clear=True):
        assert conv.get_dbf_encoding() == "latin-1"


def test_dbf_encoding_reads_env():
    with patch.dict(os.environ, {"DBF_ENCODING": "cp850"}):
        assert conv.get_dbf_encoding() == "cp850"
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `make test-unit` (or targeted pytest path).

- [ ] **Step 3: Implement in `importer/convert_dbase.py`**

```python
def get_dbf_encoding() -> str:
    return os.getenv("DBF_ENCODING", "latin-1")
```

In `load_dbf_into_postgres`, replace hardcoded encoding:

```python
dbf = DBF(dbf_path, encoding=get_dbf_encoding(), ignore_missing_memofile=True)
```

- [ ] **Step 4: Document in `.env.example` and README**

```bash
# .env.example
# DBF_ENCODING=latin-1
```

- [ ] **Step 5: Run tests and commit**

```bash
git add importer/convert_dbase.py .env.example README.md tests/test_importer_encoding.py
git commit -m "feat: configurable DBF encoding via DBF_ENCODING"
```

---

### Task 7: Makefile export targets fail loudly

**Files:**
- Modify: `Makefile:43-49`

- [ ] **Step 1: Remove `|| true` and add guard**

```makefile
export-sql: exports-dir
	@docker exec dbase_pg pg_isready -U "$$(grep ^POSTGRES_USER .env | cut -d= -f2)" >/dev/null
	@docker exec -i dbase_pg pg_dump -U "$$(grep ^POSTGRES_USER .env | cut -d= -f2)" -d "$$(grep ^POSTGRES_DB .env | cut -d= -f2)" -h localhost -p 5432 --no-owner --no-privileges > exports/schema_data.sql
	@echo "Wrote exports/schema_data.sql"

export-custom: exports-dir
	@docker exec dbase_pg pg_isready -U "$$(grep ^POSTGRES_USER .env | cut -d= -f2)" >/dev/null
	@docker exec -i dbase_pg pg_dump -U "$$(grep ^POSTGRES_USER .env | cut -d= -f2)" -d "$$(grep ^POSTGRES_DB .env | cut -d= -f2)" -h localhost -p 5432 -Fc > exports/database.dump
	@echo "Wrote exports/database.dump"
```

- [ ] **Step 2: Manual check**

With stack down: `make export-sql` → non-zero exit.  
With `make up-db` + import: succeeds and files exist.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "fix: surface pg_dump failures in export targets"
```

---

### Task 8: `fetch_public_dbf.py` exits non-zero on total failure

**Files:**
- Modify: `scripts/fetch_public_dbf.py`

- [ ] **Step 1: Write failing test** (if adding `tests/test_fetch_public_dbf.py`):

```python
def test_main_exits_1_when_all_downloads_fail(monkeypatch, tmp_path, capsys):
    import scripts.fetch_public_dbf as mod

    monkeypatch.setattr(mod, "NATURAL_EARTH_URLS", [("x", "http://invalid.example/nope.zip")])
    monkeypatch.setattr(mod, "ensure_data_dir", lambda: tmp_path)
    assert mod.main() == 1
```

- [ ] **Step 2: Implement**

```python
def main() -> int:
    outdir = ensure_data_dir()
    failures = 0
    for name, url in NATURAL_EARTH_URLS:
        try:
            download_and_extract_dbf(name, url, outdir)
        except Exception as exc:
            failures += 1
            print(f"Failed to fetch {name}: {exc}")
    if failures == len(NATURAL_EARTH_URLS):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run tests and commit**

---

## Phase 2 — Medium priority (next sprint)

**Outcome:** Safer contributor experience, clearer ops notes, optional importer naming hardening.

---

### Task 9: Document Docker socket and integration test side effects

**Files:**
- Modify: `CONTRIBUTING.md` or `README.md` → new "Testing" subsection

- [ ] Add bullets:
  - `tester` service mounts `/var/run/docker.sock` so integration tests can run nested compose; do not use on untrusted hosts.
  - `test-integration` may run `docker compose down` and remove `data/*.dbf` in teardown—stop local stacks first or use a clean clone.

- [ ] Commit: `docs: document integration test and docker.sock caveats`

---

### Task 10: Table name sanitization (implement README promise **or** keep docs-only)

**Pick one approach in a short design note before coding.**

**Option A — Implement (recommended if public demos use messy filenames)**

**Files:**
- Create: `importer/naming.py`
- Modify: `importer/convert_dbase.py`
- Create: `tests/test_importer_naming.py`

```python
# importer/naming.py
import re

_IDENT_RE = re.compile(r"[^a-z0-9_]+")


def sanitize_table_name(basename: str) -> str:
    name = basename.lower().strip()
    name = _IDENT_RE.sub("_", name)
    name = name.strip("_") or "table"
    if name[0].isdigit():
        name = f"t_{name}"
    return name[:63]  # Postgres identifier limit
```

Wire into `load_dbf_into_postgres` and add tests for `Foo-Bar.DBF`, `123data.dbf`, collision policy (document: last file wins or error—choose **error** for safety).

**Option B — Docs-only**  
Already done in Task 3; skip code.

- [ ] Commit with tests if Option A.

---

### Task 11: Column name deduplication after lowercasing

**Files:**
- Modify: `importer/convert_dbase.py` (`infer_sqlalchemy_table_from_dbf`)

- [ ] **Step 1: Failing test** — two fields that lowercase to same name → second becomes `name_2`.

- [ ] **Step 2: Implement dedup loop** when building `Column` list.

- [ ] **Step 3: Update README** if Task 3 said collisions are not handled.

---

### Task 12: Recursive `.dbf` discovery (optional)

**Files:**
- Modify: `importer/convert_dbase.py:89`

```python
dbf_paths = sorted(glob.glob("/data/**/*.dbf", recursive=True))
```

- [ ] Add test with nested `data/subdir/x.dbf` in unit test via tmp_path mount pattern or mocked glob.

---

### Task 13: CI — dependency audit job

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] Add step after image build:

```yaml
- name: pip-audit (api)
  run: docker compose run --rm --no-deps api pip install pip-audit && pip-audit -r requirements.txt
```

Repeat for `importer` or use a single `tools` image with combined audit.

- [ ] Optional: add `.github/dependabot.yml` for pip and GitHub Actions.

---

### Task 14: Pin Postgres image by digest (optional)

**Files:**
- Modify: `docker-compose.yml`

- [ ] Resolve digest: `docker pull postgres:16-alpine && docker inspect --format='{{index .RepoDigests 0}}' postgres:16-alpine`

- [ ] Set `image: postgres:16-alpine@sha256:...` and note update process in README.

---

## Phase 3 — Larger investments (roadmap epics)

Track as separate plans when prioritized; not bite-sized here.

| Epic | Scope | Key files |
|------|--------|-----------|
| **Production hardening** | API key middleware, CORS, rate limits, read-only DB user for API | `api/app/main.py`, new `api/app/auth.py`, compose overrides |
| **Richer API** | Filters, sort, cursor pagination, response metadata | `api/app/routes/dynamic.py`, OpenAPI examples |
| **Importer scale** | Chunked inserts, import metadata table (file hash, timestamp) | `importer/`, Alembic optional |
| **DX** | `.devcontainer/`, Ruff + mypy in CI | `.devcontainer/devcontainer.json`, `pyproject.toml` |
| **Observability** | JSON logs, Prometheus metrics | `api/app/main.py`, middleware |
| **Non-root containers** | `USER` in Dockerfiles | all `*/Dockerfile` |

---

## Verification checklist (run after each phase)

```bash
make format-check
make test-unit
make test-integration   # longer; needs Docker socket
make demo-public        # smoke: fetch + import + API
curl -s http://localhost:8000/health | jq .
```

---

## Self-review (plan vs review spec)

| Review item | Task |
|-------------|------|
| Duplicate `api/app/README.md` | Task 1 |
| Broken `test-unit` PYTHONPATH | Task 2 |
| README vs code (naming, collisions) | Task 3, 10, 11 |
| Security / production callout | Task 3 |
| Shallow `/health` | Task 4 |
| Unused `python-dotenv` | Task 5 |
| `DBF_ENCODING` | Task 6 |
| Export `|| true` | Task 7 |
| `fetch_public_dbf` exit code | Task 8 |
| Docker socket / integration side effects | Task 9 |
| Flat-only import | Task 12 |
| pip-audit / Dependabot | Task 13 |
| Postgres digest pin | Task 14 |
| Puppeteer path confusion | Task 3 (docs) |
| Production API auth, richer API, observability | Phase 3 epics |

**Placeholder scan:** No TBD steps in Phase 1–2 tasks.

---

## Suggested commit / PR breakdown

1. PR: Phase 1 Tasks 1–3 (docs + Makefile)
2. PR: Task 4 (health + DB)
3. PR: Tasks 5–8 (deps, encoding, exports, fetch)
4. PR: Phase 2 (medium items) as ready
