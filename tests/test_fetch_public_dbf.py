def test_main_exits_1_when_all_downloads_fail(monkeypatch, tmp_path, capsys):
    import scripts.fetch_public_dbf as mod

    monkeypatch.setattr(mod, "NATURAL_EARTH_URLS", [("x", "http://invalid.example/nope.zip")])
    monkeypatch.setattr(mod, "ensure_data_dir", lambda: tmp_path)
    assert mod.main() == 1
