from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    LargeBinary,
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


def test_float_fields_stay_numeric_even_without_decimals():
    # dbfread parseF returns float. An integer column rounds or overflows.
    mapped = map_dbase_type(FakeField("Amt", "F", length=9, decimal_count=0))
    assert isinstance(mapped, Numeric)
    assert not isinstance(mapped, Integer)


def test_memo_pointer_fields_are_not_truncated_to_pointer_width():
    assert isinstance(map_dbase_type(FakeField("Ole", "G", length=10)), LargeBinary)
    assert isinstance(map_dbase_type(FakeField("Pic", "P", length=10)), LargeBinary)
    memo_b = map_dbase_type(FakeField("Blob", "B", length=10), dbversion=0x03)
    assert isinstance(memo_b, LargeBinary)
    vfp_double = map_dbase_type(FakeField("Dbl", "B", length=8), dbversion=0x30)
    assert isinstance(vfp_double, Float)


def test_infer_uses_file_version_for_b_fields():
    class Header:
        dbversion = 0x30

    dbf = FakeDBF([FakeField("Dbl", "B", length=8)])
    dbf.header = Header()
    table = infer_sqlalchemy_table_from_dbf(dbf, MetaData(), "sample")
    assert isinstance(table.c.dbl.type, Float)


def test_map_dbase_type_string_default_length():
    s = map_dbase_type(FakeField("X", "C", length=None))
    assert isinstance(s, String)


def test_infer_table_renames_source_dbf_recno_column():
    fields = [FakeField("dbf_recno", "N", length=4), FakeField("Name", "C", length=20)]
    table = infer_sqlalchemy_table_from_dbf(FakeDBF(fields), MetaData(), "sample")
    assert [c.name for c in table.columns] == ["dbf_recno_2", "name", "dbf_recno"]
