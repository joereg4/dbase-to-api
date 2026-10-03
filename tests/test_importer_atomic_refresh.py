"""A failed reload must leave the previous table contents intact."""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import StatementError

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


def test_failed_reload_keeps_previous_table(pg_engine, tmp_path):
    table = pg_engine.track_table(f"pytest_keep_{uuid.uuid4().hex[:8]}")
    dbf_path = tmp_path / f"{table}.dbf"
    _write_sample_dbf(dbf_path)

    load_dbf_into_postgres(pg_engine, str(dbf_path))

    def fail_insert(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT"):
            raise RuntimeError("simulated insert failure")

    event.listen(pg_engine, "before_cursor_execute", fail_insert)
    try:
        with pytest.raises((RuntimeError, StatementError)):
            load_dbf_into_postgres(pg_engine, str(dbf_path))
    finally:
        event.remove(pg_engine, "before_cursor_execute", fail_insert)

    with pg_engine.begin() as conn:
        rows = (
            conn.execute(text(f'SELECT id, name FROM public."{table}" ORDER BY dbf_recno'))
            .mappings()
            .all()
        )

    assert [dict(r) for r in rows] == [
        {"id": 1, "name": "Alpha"},
        {"id": 2, "name": "Beta"},
    ]
