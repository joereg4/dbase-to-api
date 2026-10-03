from sqlalchemy import text


def test_identifier_preparer_escapes_embedded_quotes(pg_engine):
    """The route relies on dialect.identifier_preparer.quote to defuse hostile
    table names. Verify that a name containing a double-quote is escaped by
    doubling, not dropped or truncated."""
    preparer = pg_engine.dialect.identifier_preparer

    hostile = 'evil"; DROP TABLE users; --'
    quoted = preparer.quote(hostile)

    assert quoted.startswith('"') and quoted.endswith('"')
    assert '""' in quoted  # standard SQL escape: embedded " becomes ""
    # No un-escaped quote can appear in the middle of the identifier.
    inner = quoted[1:-1]
    i = 0
    while i < len(inner):
        if inner[i] == '"':
            assert i + 1 < len(inner) and inner[i + 1] == '"', "unescaped quote leaked through"
            i += 2
        else:
            i += 1


def test_identifier_preparer_roundtrips_quoted_table(pg_engine):
    """Create a table whose name contains a quote using the preparer, then read
    from it — proves the escaping is actually valid SQL."""
    preparer = pg_engine.dialect.identifier_preparer
    name = 'weird"name'
    quoted = preparer.quote(name)

    try:
        with pg_engine.begin() as conn:
            conn.execute(text(f"CREATE TABLE {quoted} (id INTEGER)"))
            conn.execute(text(f"INSERT INTO {quoted} (id) VALUES (42)"))
            got = conn.execute(text(f"SELECT id FROM {quoted}")).scalar()
        assert got == 42
    finally:
        with pg_engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {quoted}"))
