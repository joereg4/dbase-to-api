from sqlalchemy import Integer, String, Numeric, Date, DateTime, Boolean


# We test the pure functions without requiring a real DBF file or a database.
from importer.convert_dbase import map_dbase_type, infer_sqlalchemy_table_from_dbf


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
    assert isinstance(map_dbase_type(FakeField("A", "N", length=10)), Integer)
    assert isinstance(map_dbase_type(FakeField("B", "F", length=12, decimal_count=2)), Numeric)
    assert isinstance(map_dbase_type(FakeField("C", "D")), Date)
    assert isinstance(map_dbase_type(FakeField("D", "T")), DateTime)
    assert isinstance(map_dbase_type(FakeField("E", "L")), Boolean)
    # default to String when unrecognized
    s = map_dbase_type(FakeField("F", "C", length=40))
    assert isinstance(s, String)


def test_infer_table_from_dbf_lowercases_names_and_creates_columns():
    fields = [
        FakeField("ID", "N", length=10),
        FakeField("Name", "C", length=255),
        FakeField("Amt", "F", length=12, decimal_count=2),
    ]
    dbf = FakeDBF(fields)

    from sqlalchemy import MetaData

    md = MetaData()
    table = infer_sqlalchemy_table_from_dbf(dbf, md, "sample")

    assert table.name == "sample"
    col_names = [c.name for c in table.columns]
    assert col_names == ["id", "name", "amt"]

    # spot-check types
    assert isinstance(table.c.id.type, Integer)
    assert isinstance(table.c.name.type, String)
    assert isinstance(table.c.amt.type, Numeric)


def test_map_dbase_type_string_default_length():
    s = map_dbase_type(FakeField("X", "C", length=None))
    # default should be a String with some positive length
    assert isinstance(s, String)
