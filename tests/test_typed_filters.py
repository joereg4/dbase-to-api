"""Equality filters must bind the column's SQL type, including on PostgreSQL."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import Boolean, Column, Date, Integer, MetaData, Numeric, String, Table
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from api.app.routes.dynamic import list_rows


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


def test_equality_filters_match_typed_columns_on_postgres(pg_engine):
    table_name = pg_engine.track_table(f"pytest_filt_{uuid.uuid4().hex[:8]}")
    people = Table(
        table_name,
        MetaData(),
        Column("id", Integer),
        Column("active", Boolean),
        Column("born", Date),
        Column("amt", Numeric(10, 2)),
        Column("dbf_recno", Integer, primary_key=True),
        schema="public",
    )
    people.create(pg_engine)
    with pg_engine.begin() as conn:
        conn.execute(
            people.insert(),
            [
                {
                    "id": 1,
                    "active": True,
                    "born": date(2020, 1, 2),
                    "amt": Decimal("1.50"),
                    "dbf_recno": 1,
                },
                {
                    "id": 2,
                    "active": False,
                    "born": date(2021, 3, 4),
                    "amt": Decimal("2.00"),
                    "dbf_recno": 2,
                },
            ],
        )

    db = sessionmaker(bind=pg_engine)()
    try:
        result = list_rows(
            table_name,
            request=_request("id=1&active=true&born=2020-01-02&amt=1.50"),
            db=db,
            limit=50,
            offset=0,
        )
    finally:
        db.close()

    assert result["count"] == 1
    assert result["items"][0]["id"] == 1
    assert result["items"][0]["active"] is True


def test_mistyped_filter_returns_400_on_postgres(pg_engine):
    table_name = pg_engine.track_table(f"pytest_bad_{uuid.uuid4().hex[:8]}")
    people = Table(
        table_name,
        MetaData(),
        Column("id", Integer),
        Column("dbf_recno", Integer, primary_key=True),
        schema="public",
    )
    people.create(pg_engine)
    with pg_engine.begin() as conn:
        conn.execute(people.insert(), [{"id": 1, "dbf_recno": 1}])

    db = sessionmaker(bind=pg_engine)()
    try:
        with pytest.raises(HTTPException) as exc:
            list_rows(
                table_name,
                request=_request("id=nope"),
                db=db,
                limit=50,
                offset=0,
            )
    finally:
        db.close()
    assert exc.value.status_code == 400


def test_reserved_column_name_filters_through_prefix(pg_engine):
    table_name = pg_engine.track_table(f"pytest_sort_{uuid.uuid4().hex[:8]}")
    people = Table(
        table_name,
        MetaData(),
        Column("sort", String(20)),
        Column("dbf_recno", Integer, primary_key=True),
        schema="public",
    )
    people.create(pg_engine)
    with pg_engine.begin() as conn:
        conn.execute(
            people.insert(),
            [
                {"sort": "keep", "dbf_recno": 1},
                {"sort": "drop", "dbf_recno": 2},
            ],
        )
    db = sessionmaker(bind=pg_engine)()
    try:
        result = list_rows(
            table_name,
            request=_request("filter.sort=keep"),
            db=db,
            limit=50,
            offset=0,
        )
    finally:
        db.close()

    assert result["count"] == 1
    assert result["items"][0]["sort"] == "keep"
