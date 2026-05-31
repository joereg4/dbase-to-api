from importer.convert_dbase import infer_sqlalchemy_table_from_dbf
from tests.test_importer_unit import FakeDBF, FakeField


def test_infer_table_deduplicates_column_names_after_lowercasing():
    fields = [
        FakeField("NAME", "C", length=40),
        FakeField("Name", "C", length=40),
        FakeField("name", "C", length=40),
    ]
    dbf = FakeDBF(fields)

    from sqlalchemy import MetaData

    md = MetaData()
    table = infer_sqlalchemy_table_from_dbf(dbf, md, "sample")

    col_names = [c.name for c in table.columns]
    assert col_names == ["name", "name_2", "name_3"]
