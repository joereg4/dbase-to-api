import logging
import uuid

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


def test_load_warns_when_memofilename_missing(pg_engine, tmp_path, caplog, monkeypatch):
    table = pg_engine.track_table(f"pytest_memo_{uuid.uuid4().hex[:8]}")
    monkeypatch.setattr(
        convert_dbase,
        "DBF",
        lambda *a, **k: FakeMemoDBF(
            [FakeField("Notes", "M", length=10)], memofilename=None, memo=object()
        ),
    )

    with caplog.at_level(logging.WARNING, logger="importer"):
        convert_dbase.load_dbf_into_postgres(pg_engine, str(tmp_path / f"{table}.dbf"))

    assert any("Memo file missing" in r.message for r in caplog.records)


def test_load_does_not_warn_when_memofile_is_present(pg_engine, tmp_path, caplog, monkeypatch):
    table = pg_engine.track_table(f"pytest_memo_{uuid.uuid4().hex[:8]}")
    monkeypatch.setattr(
        convert_dbase,
        "DBF",
        lambda *a, **k: FakeMemoDBF(
            [FakeField("Notes", "M", length=10)], memofilename="notes.dbt", memo=None
        ),
    )

    with caplog.at_level(logging.WARNING, logger="importer"):
        convert_dbase.load_dbf_into_postgres(pg_engine, str(tmp_path / f"{table}.dbf"))

    assert not any("Memo file missing" in r.message for r in caplog.records)
