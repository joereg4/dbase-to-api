from importer.convert_dbase import normalize_dbf_rows
from tests.test_importer_unit import FakeDBF, FakeField


def test_normalize_dbf_rows_assigns_one_based_recno():
    dbf = FakeDBF([FakeField("ID", "N", length=4), FakeField("Name", "C", length=20)])
    rows = [{"ID": 10, "Name": "Alpha"}, {"ID": 20, "Name": "Beta"}]

    normalized = normalize_dbf_rows(rows, dbf)

    assert normalized == [
        {"id": 10, "name": "Alpha", "dbf_recno": 1},
        {"id": 20, "name": "Beta", "dbf_recno": 2},
    ]


def test_normalize_dbf_rows_suffixes_source_dbf_recno_field():
    dbf = FakeDBF([FakeField("dbf_recno", "N", length=4), FakeField("Name", "C", length=20)])
    rows = [{"dbf_recno": 99, "Name": "Alpha"}]

    normalized = normalize_dbf_rows(rows, dbf)

    assert normalized == [{"dbf_recno_2": 99, "name": "Alpha", "dbf_recno": 1}]
