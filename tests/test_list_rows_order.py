"""list_rows orders by dbf_recno so page contents stay stable."""

import uuid

from sqlalchemy import Column, Integer, MetaData, String, Table
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from api.app.routes.dynamic import list_rows, order_by_sql, stable_order_sql


def _request(query: str = "") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": query.encode(),
        }
    )


def test_stable_order_sql_prefers_dbf_recno(pg_engine):
    preparer = pg_engine.dialect.identifier_preparer
    assert stable_order_sql(["id", "name", "dbf_recno"], preparer) == preparer.quote("dbf_recno")


def test_stable_order_sql_falls_back_to_all_columns(pg_engine):
    preparer = pg_engine.dialect.identifier_preparer
    assert stable_order_sql(["id", "name"], preparer) == (
        f"{preparer.quote('id')}, {preparer.quote('name')}"
    )


def test_order_by_sql_sort_desc_with_recno_tiebreak(pg_engine):
    preparer = pg_engine.dialect.identifier_preparer
    got = order_by_sql(["name", "dbf_recno"], preparer, "-name")
    assert got == f"{preparer.quote('name')} DESC, {preparer.quote('dbf_recno')} ASC"


def test_list_rows_orders_by_dbf_recno_despite_insert_order(pg_engine):
    table_name = pg_engine.track_table(f"pytest_order_{uuid.uuid4().hex[:8]}")
    people = Table(
        table_name,
        MetaData(),
        Column("name", String(20)),
        Column("dbf_recno", Integer, primary_key=True),
        schema="public",
    )
    people.create(pg_engine)
    with pg_engine.begin() as conn:
        # Insert out of source order so heap order would put Beta first.
        conn.execute(people.insert(), [{"name": "Beta", "dbf_recno": 2}])
        conn.execute(people.insert(), [{"name": "Alpha", "dbf_recno": 1}])

    db = sessionmaker(bind=pg_engine)()
    try:
        result = list_rows(table_name, request=_request(), db=db, limit=50, offset=0)
    finally:
        db.close()

    assert result["count"] == 2
    assert [r["dbf_recno"] for r in result["items"]] == [1, 2]
    assert [r["name"] for r in result["items"]] == ["Alpha", "Beta"]
