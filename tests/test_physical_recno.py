"""dbf_recno is the physical xBase slot, so a deleted record keeps its number."""

import uuid

from sqlalchemy import text

from importer.convert_dbase import load_dbf_into_postgres, normalize_dbf_rows
from tests.dbf_bytes import write_dbf
from tests.test_importer_unit import FakeDBF, FakeField


def test_normalize_uses_supplied_physical_record_numbers():
    dbf = FakeDBF([FakeField("Name", "C", length=10)])
    rows = [{"Name": "Alpha"}, {"Name": "Gamma"}]

    normalized = normalize_dbf_rows(rows, dbf, recnos=[1, 3])

    assert [row["dbf_recno"] for row in normalized] == [1, 3]


def _deleted_middle(path) -> None:
    write_dbf(
        path,
        [("name", "C", 10, 0)],
        [
            (False, ["Alpha"]),
            (True, ["Beta"]),
            (False, ["Gamma"]),
        ],
    )


def test_deleted_slot_keeps_its_record_number_on_postgres(pg_engine, tmp_path):
    table = pg_engine.track_table(f"pytest_rec_{uuid.uuid4().hex[:8]}")
    path = tmp_path / f"{table}.dbf"
    _deleted_middle(path)

    load_dbf_into_postgres(pg_engine, str(path))

    with pg_engine.connect() as conn:
        rows = conn.execute(
            text(f'SELECT name, dbf_recno FROM public."{table}" ORDER BY dbf_recno')
        ).all()
    assert rows == [("Alpha", 1), ("Gamma", 3)]
