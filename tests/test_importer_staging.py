"""Staging must not collide with a live import or exceed 63 bytes."""

import uuid
from pathlib import Path

from sqlalchemy import create_engine, text

from importer.convert_dbase import load_dbf_into_postgres
from importer.naming import sanitize_table_name
from tests.dbf_bytes import write_dbf


def _people(path: Path, name: str) -> None:
    write_dbf(path, [("name", "C", 10, 0)], [(False, [name])])


def test_sqlite_staging_name_cannot_be_a_sanitized_basename():
    from importer.naming import staging_location

    schema, staging = staging_location("sqlite", "customers")
    assert schema is None
    assert sanitize_table_name(staging) != staging


def test_postgres_staging_reuses_the_live_name_in_another_schema():
    from importer.naming import staging_location

    table = "a" * 63
    assert staging_location("postgresql", table) == ("import_staging", table)


def test_import_does_not_drop_a_table_named_with_the_loading_suffix(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    loading = tmp_path / "customers__loading.dbf"
    live = tmp_path / "customers.dbf"
    _people(loading, "keep")
    _people(live, "fresh")

    load_dbf_into_postgres(engine, str(loading))
    load_dbf_into_postgres(engine, str(live))

    with engine.connect() as conn:
        kept = conn.execute(text("SELECT name FROM customers__loading")).scalar_one()
        fresh = conn.execute(text("SELECT name FROM customers")).scalar_one()
    assert kept == "keep"
    assert fresh == "fresh"


def test_postgres_import_does_not_drop_a_loading_suffix_table(pg_engine, tmp_path):
    live = pg_engine.track_table(f"pytest_live_{uuid.uuid4().hex[:8]}")
    loading = pg_engine.track_table(f"{live}__loading")
    _people(tmp_path / f"{loading}.dbf", "keep")
    _people(tmp_path / f"{live}.dbf", "fresh")

    load_dbf_into_postgres(pg_engine, str(tmp_path / f"{loading}.dbf"))
    load_dbf_into_postgres(pg_engine, str(tmp_path / f"{live}.dbf"))

    with pg_engine.connect() as conn:
        kept = conn.execute(text(f'SELECT name FROM public."{loading}"')).scalar_one()
        fresh = conn.execute(text(f'SELECT name FROM public."{live}"')).scalar_one()
    assert kept == "keep"
    assert fresh == "fresh"


def test_63_byte_table_name_imports_on_postgres(pg_engine, tmp_path):
    table = pg_engine.track_table("n" * 63)
    path = tmp_path / f"{table}.dbf"
    _people(path, "ok")

    load_dbf_into_postgres(pg_engine, str(path))

    with pg_engine.connect() as conn:
        got = conn.execute(text(f'SELECT name FROM public."{table}"')).scalar_one()
        staging_left = conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'import_staging' AND table_name = :t"
            ),
            {"t": table},
        ).first()
    assert got == "ok"
    assert staging_left is None


def test_failed_reload_keeps_previous_table_on_postgres(pg_engine, tmp_path):
    import pytest
    from sqlalchemy import event
    from sqlalchemy.exc import StatementError

    table = pg_engine.track_table(f"pytest_keep_{uuid.uuid4().hex[:8]}")
    path = tmp_path / f"{table}.dbf"
    _people(path, "Alpha")
    load_dbf_into_postgres(pg_engine, str(path))

    def fail_insert(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT"):
            raise RuntimeError("simulated insert failure")

    event.listen(pg_engine, "before_cursor_execute", fail_insert)
    try:
        with pytest.raises((RuntimeError, StatementError)):
            load_dbf_into_postgres(pg_engine, str(path))
    finally:
        event.remove(pg_engine, "before_cursor_execute", fail_insert)

    with pg_engine.connect() as conn:
        got = conn.execute(text(f'SELECT name FROM public."{table}"')).scalar_one()
    assert got == "Alpha"
