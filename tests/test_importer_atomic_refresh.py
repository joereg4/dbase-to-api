"""A failed reload must leave the previous table contents intact."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, text
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


def test_failed_reload_keeps_previous_table(tmp_path):
    dbf_path = tmp_path / "people.dbf"
    _write_sample_dbf(dbf_path)

    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    load_dbf_into_postgres(engine, str(dbf_path))

    def fail_insert(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT"):
            raise RuntimeError("simulated insert failure")

    event.listen(engine, "before_cursor_execute", fail_insert)
    try:
        with pytest.raises((RuntimeError, StatementError)):
            load_dbf_into_postgres(engine, str(dbf_path))
    finally:
        event.remove(engine, "before_cursor_execute", fail_insert)

    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, name FROM people ORDER BY dbf_recno")).mappings().all()

    assert [dict(r) for r in rows] == [
        {"id": 1, "name": "Alpha"},
        {"id": 2, "name": "Beta"},
    ]
