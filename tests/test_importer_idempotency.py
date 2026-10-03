"""Verify that load_dbf_into_postgres drops+recreates the table so repeated
runs leave the database in the same state (no row duplication)."""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

try:
    from dbf import Table as DbfTable, READ_WRITE
except ImportError:  # pragma: no cover
    pytest.skip("dbf library not installed", allow_module_level=True)

from importer.convert_dbase import load_dbf_into_postgres


def _write_sample_dbf(path: Path) -> None:
    table = DbfTable(str(path), "id N(4,0); name C(20)")
    table.open(mode=READ_WRITE)
    try:
        table.append((1, "Alpha"))
        table.append((2, "Beta"))
    finally:
        table.close()


def test_reimport_does_not_duplicate_rows(pg_engine, tmp_path):
    table = pg_engine.track_table(f"pytest_idem_{uuid.uuid4().hex[:8]}")
    dbf_path = tmp_path / f"{table}.dbf"
    _write_sample_dbf(dbf_path)

    load_dbf_into_postgres(pg_engine, str(dbf_path))
    load_dbf_into_postgres(pg_engine, str(dbf_path))

    with pg_engine.begin() as conn:
        count = conn.execute(text(f'SELECT COUNT(*) FROM public."{table}"')).scalar()
    assert count == 2
