"""Verify that load_dbf_into_postgres drops+recreates the table so repeated
runs leave the database in the same state (no row duplication)."""
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

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


def test_reimport_does_not_duplicate_rows(tmp_path):
    dbf_path = tmp_path / "people.dbf"
    _write_sample_dbf(dbf_path)

    engine = create_engine(f"sqlite:///{tmp_path/'db.sqlite'}")

    load_dbf_into_postgres(engine, str(dbf_path))
    load_dbf_into_postgres(engine, str(dbf_path))

    with engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM people")).scalar()
    assert count == 2
