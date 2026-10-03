"""Shared pytest helpers."""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def compose_test_env(base: dict | None = None) -> dict:
    """Build docker-compose env for integration tests from `.env.example` defaults."""
    env = dict(base or os.environ)
    env.pop("COMPOSE_FILE", None)
    example = PROJECT_ROOT / ".env.example"
    for line in example.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env.setdefault(key.strip(), value.strip())
    return env


def _postgres_url() -> str:
    return os.getenv(
        "TEST_DATABASE_URL",
        os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@db:5432/dbase"),
    )


@pytest.fixture()
def pg_engine():
    """Connect to the compose database. Skip when it is unreachable."""
    engine = create_engine(_postgres_url(), pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        engine.dispose()
        pytest.skip(f"PostgreSQL not available: {exc}")

    created: list[str] = []

    def track(name: str) -> str:
        created.append(name)
        return name

    engine.track_table = track  # type: ignore[attr-defined]
    try:
        yield engine
    finally:
        with engine.begin() as conn:
            schema_exists = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.schemata "
                    "WHERE schema_name = 'import_staging'"
                )
            ).first()
            for name in created:
                conn.execute(text(f'DROP TABLE IF EXISTS public."{name}" CASCADE'))
                if schema_exists:
                    conn.execute(text(f'DROP TABLE IF EXISTS import_staging."{name}" CASCADE'))
        engine.dispose()
