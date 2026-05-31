"""Verify importer main() exit codes and error handling."""

from pathlib import Path

import pytest

try:
    from dbf import Table as DbfTable, READ_WRITE
except ImportError:  # pragma: no cover
    pytest.skip("dbf library not installed", allow_module_level=True)

from importer import convert_dbase


def _write_sample_dbf(path: Path) -> None:
    table = DbfTable(str(path), "id N(4,0); name C(20)")
    table.open(mode=READ_WRITE)
    try:
        table.append((1, "Alpha"))
    finally:
        table.close()


def test_main_returns_zero_when_no_dbf_files(tmp_path, monkeypatch):
    monkeypatch.setattr(convert_dbase.glob, "glob", lambda _pattern, **kwargs: [])
    monkeypatch.setattr(
        convert_dbase,
        "get_database_url",
        lambda: f"sqlite:///{tmp_path/'db.sqlite'}",
    )
    assert convert_dbase.main() == 0


def test_main_discovers_dbf_files_recursively(tmp_path, monkeypatch):
    nested = tmp_path / "subdir"
    nested.mkdir()
    good = nested / "nested.dbf"
    _write_sample_dbf(good)

    monkeypatch.setattr(
        convert_dbase,
        "get_database_url",
        lambda: f"sqlite:///{tmp_path/'db.sqlite'}",
    )

    real_glob = convert_dbase.glob.glob

    def capture_glob(pattern, **kwargs):
        if pattern == "/data/**/*.dbf":
            assert kwargs.get("recursive") is True
            return real_glob(str(nested / "*.dbf"))
        return real_glob(pattern, **kwargs)

    monkeypatch.setattr(convert_dbase.glob, "glob", capture_glob)
    assert convert_dbase.main() == 0


def test_main_returns_nonzero_when_any_file_fails(tmp_path, monkeypatch, caplog):
    good = tmp_path / "good.dbf"
    _write_sample_dbf(good)
    bad_path = str(tmp_path / "broken.dbf")

    monkeypatch.setattr(
        convert_dbase.glob, "glob", lambda _pattern, **kwargs: [str(good), bad_path]
    )
    monkeypatch.setattr(
        convert_dbase,
        "get_database_url",
        lambda: f"sqlite:///{tmp_path/'db.sqlite'}",
    )

    real_loader = convert_dbase.load_dbf_into_postgres

    def flaky_loader(engine, path):
        if path == bad_path:
            raise RuntimeError("synthetic failure")
        return real_loader(engine, path)

    monkeypatch.setattr(convert_dbase, "load_dbf_into_postgres", flaky_loader)

    with caplog.at_level("ERROR", logger="importer"):
        rc = convert_dbase.main()

    assert rc == 1
    messages = "\n".join(r.getMessage() for r in caplog.records)
    assert "broken.dbf" in messages
    assert "synthetic failure" in caplog.text  # includes formatted exception
