import logging

from sqlalchemy import create_engine

from importer import convert_dbase
from tests.test_importer_unit import FakeField


class FakeMemoDBF:
    def __init__(self, fields, memofilename, memo=None):
        self.fields = fields
        self.memofilename = memofilename
        # dbfread never sets this. A truthy value must not silence the warning.
        self.memo = memo

    def __iter__(self):
        return iter([])


def test_load_warns_when_memofilename_missing(tmp_path, caplog, monkeypatch):
    monkeypatch.setattr(
        convert_dbase,
        "DBF",
        lambda *a, **k: FakeMemoDBF(
            [FakeField("Notes", "M", length=10)], memofilename=None, memo=object()
        ),
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")

    with caplog.at_level(logging.WARNING, logger="importer"):
        convert_dbase.load_dbf_into_postgres(engine, str(tmp_path / "notes.dbf"))

    assert any("Memo file missing" in r.message for r in caplog.records)


def test_load_does_not_warn_when_memofile_is_present(tmp_path, caplog, monkeypatch):
    monkeypatch.setattr(
        convert_dbase,
        "DBF",
        lambda *a, **k: FakeMemoDBF(
            [FakeField("Notes", "M", length=10)], memofilename="notes.dbt", memo=None
        ),
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")

    with caplog.at_level(logging.WARNING, logger="importer"):
        convert_dbase.load_dbf_into_postgres(engine, str(tmp_path / "notes.dbf"))

    assert not any("Memo file missing" in r.message for r in caplog.records)
