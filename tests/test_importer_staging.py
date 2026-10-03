"""Staging must not collide with a live import or exceed 63 bytes."""

import uuid
from pathlib import Path

from sqlalchemy import text

from importer.convert_dbase import load_dbf_into_postgres
from tests.dbf_bytes import write_dbf


def _people(path: Path, name: str) -> None:
    write_dbf(path, [("name", "C", 10, 0)], [(False, [name])])


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
