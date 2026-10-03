"""Whole-number F values must survive a real PostgreSQL insert."""

import uuid

from sqlalchemy import text

from importer.convert_dbase import load_dbf_into_postgres
from tests.dbf_bytes import write_dbf


def test_float_field_values_round_trip_on_postgres(pg_engine, tmp_path):
    table = pg_engine.track_table(f"pytest_f_{uuid.uuid4().hex[:8]}")
    path = tmp_path / f"{table}.dbf"
    write_dbf(
        path,
        [("amt", "F", 9, 0), ("name", "C", 5, 0)],
        [
            (False, ["1.5", "half"]),
            (False, ["1.2345e20", "huge"]),
        ],
    )

    load_dbf_into_postgres(pg_engine, str(path))

    with pg_engine.connect() as conn:
        rows = (
            conn.execute(text(f'SELECT amt, name FROM public."{table}" ORDER BY dbf_recno'))
            .mappings()
            .all()
        )
    amounts = [row["amt"] for row in rows]
    assert float(amounts[0]) == 1.5
    assert float(amounts[1]) == float("1.2345e20")
    assert [row["name"] for row in rows] == ["half", "huge"]
