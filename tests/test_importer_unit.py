from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
)

# Pure-function tests: no real DBF file or database required.
from importer.convert_dbase import infer_sqlalchemy_table_from_dbf, map_dbase_type


class FakeField:
    def __init__(
        self, name: str, ftype: str, length: int | None = None, decimal_count: int | None = None
    ):
        self.name = name
        self.type = ftype
        self.length = length
        self.decimal_count = decimal_count


class FakeDBF:
    def __init__(self, fields):
        self.fields = fields


def test_map_dbase_type_basic_mappings():
    assert isinstance(map_dbase_type(FakeField("A", "N", length=9)), Integer)
    assert isinstance(map_dbase_type(FakeField("A10", "N", length=10)), BigInteger)
    assert isinstance(map_dbase_type(FakeField("A20", "N", length=20)), Numeric)
    assert isinstance(map_dbase_type(FakeField("B", "F", length=12, decimal_count=2)), Numeric)
    assert isinstance(map_dbase_type(FakeField("C", "D")), Date)
    assert isinstance(map_dbase_type(FakeField("D", "T")), DateTime)
    assert isinstance(map_dbase_type(FakeField("E", "L")), Boolean)
    assert isinstance(map_dbase_type(FakeField("Notes", "M", length=10)), Text)
    # Unrecognized / character → String
    s = map_dbase_type(FakeField("F", "C", length=40))
    assert isinstance(s, String)


def test_infer_table_from_dbf_lowercases_names_and_creates_columns():
    fields = [
        FakeField("ID", "N", length=10),
        FakeField("Name", "C", length=255),
        FakeField("Amt", "F", length=12, decimal_count=2),
    ]
    table = infer_sqlalchemy_table_from_dbf(FakeDBF(fields), MetaData(), "sample")

    assert table.name == "sample"
    assert [c.name for c in table.columns] == ["id", "name", "amt", "dbf_recno"]
    assert isinstance(table.c.id.type, BigInteger)
    assert isinstance(table.c.name.type, String)
    assert isinstance(table.c.amt.type, Numeric)
    assert isinstance(table.c.dbf_recno.type, Integer)
    assert table.c.dbf_recno.primary_key


def test_map_dbase_type_string_default_length():
    s = map_dbase_type(FakeField("X", "C", length=None))
    assert isinstance(s, String)


def test_infer_table_renames_source_dbf_recno_column():
    fields = [FakeField("dbf_recno", "N", length=4), FakeField("Name", "C", length=20)]
    table = infer_sqlalchemy_table_from_dbf(FakeDBF(fields), MetaData(), "sample")
    assert [c.name for c in table.columns] == ["dbf_recno_2", "name", "dbf_recno"]
