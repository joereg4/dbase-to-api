import logging

from sqlalchemy import create_engine

from importer import convert_dbase
from tests.test_importer_unit import FakeField


class FakeMemoDBF:
    fields = [FakeField("Notes", "M", length=10)]
    memo = None

    def __iter__(self):
        return iter([])


def test_load_warns_when_memo_file_missing(tmp_path, caplog, monkeypatch):
    monkeypatch.setattr(convert_dbase, "DBF", lambda *a, **k: FakeMemoDBF())
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    dbf_path = str(tmp_path / "notes.dbf")

    with caplog.at_level(logging.WARNING, logger="importer"):
        convert_dbase.load_dbf_into_postgres(engine, dbf_path)

    assert any("Memo file missing" in r.message for r in caplog.records)
