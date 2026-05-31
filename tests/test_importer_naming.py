from importer.naming import sanitize_table_name


def test_sanitize_table_name_lowercases_and_strips():
    assert sanitize_table_name("Customers") == "customers"


def test_sanitize_table_name_replaces_non_alphanumeric():
    assert sanitize_table_name("Foo-Bar") == "foo_bar"


def test_sanitize_table_name_prefixes_leading_digit():
    assert sanitize_table_name("123data") == "t_123data"


def test_sanitize_table_name_empty_after_strip_becomes_table():
    assert sanitize_table_name("---") == "table"


def test_sanitize_table_name_truncates_to_postgres_limit():
    long_name = "a" * 80
    assert len(sanitize_table_name(long_name)) == 63


def test_main_errors_on_sanitized_table_name_collision(tmp_path, monkeypatch, caplog):
    from importer import convert_dbase

    path_a = str(tmp_path / "foo-bar.dbf")
    path_b = str(tmp_path / "foo_bar.dbf")

    monkeypatch.setattr(
        convert_dbase.glob,
        "glob",
        lambda _pattern, **kwargs: sorted([path_a, path_b]),
    )
    monkeypatch.setattr(
        convert_dbase,
        "get_database_url",
        lambda: f"sqlite:///{tmp_path/'db.sqlite'}",
    )

    loader_calls = []

    def track_loader(engine, path):
        loader_calls.append(path)

    monkeypatch.setattr(convert_dbase, "load_dbf_into_postgres", track_loader)

    with caplog.at_level("ERROR", logger="importer"):
        rc = convert_dbase.main()

    assert rc == 1
    assert len(loader_calls) == 1
    assert "collision" in caplog.text.lower()
