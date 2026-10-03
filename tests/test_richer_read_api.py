"""Unit tests for get-by-recno, filters, sort, and the rows envelope."""

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi import HTTPException
from sqlalchemy import Boolean, Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request

from api.app.routes.dynamic import get_row, list_rows, parse_equality_filters


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


@contextmanager
def _people_db() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    people = Table(
        "people",
        MetaData(),
        Column("name", String(20)),
        Column("active", Boolean),
        Column("dbf_recno", Integer, primary_key=True),
    )
    people.create(engine)
    with engine.begin() as conn:
        conn.execute(
            people.insert(),
            [
                {"name": "Alpha", "active": True, "dbf_recno": 1},
                {"name": "Beta", "active": False, "dbf_recno": 2},
                {"name": "Gamma", "active": True, "dbf_recno": 3},
            ],
        )
    db = sessionmaker(bind=engine)()
    try:
        yield db
    finally:
        db.close()


def test_parse_equality_filters_rejects_unknown_column():
    with pytest.raises(HTTPException) as exc:
        parse_equality_filters({"name": "Alpha", "nope": "x"}, ["name", "dbf_recno"])
    assert exc.value.status_code == 400


def test_get_row_by_dbf_recno():
    with _people_db() as db:
        row = get_row("people", 2, db=db)
    assert row["name"] == "Beta"
    assert row["dbf_recno"] == 2


def test_get_row_missing_returns_404():
    with _people_db() as db:
        with pytest.raises(HTTPException) as exc:
            get_row("people", 99, db=db)
    assert exc.value.status_code == 404


def test_list_rows_envelope_and_filter():
    with _people_db() as db:
        result = list_rows(
            "people",
            request=_request("name=Alpha"),
            db=db,
            limit=50,
            offset=0,
        )

    assert result["limit"] == 50
    assert result["offset"] == 0
    assert result["count"] == 1
    assert [r["name"] for r in result["items"]] == ["Alpha"]


def test_list_rows_sort_descending():
    with _people_db() as db:
        result = list_rows(
            "people",
            request=_request(),
            db=db,
            limit=50,
            offset=0,
            sort="-name",
        )

    assert [r["name"] for r in result["items"]] == ["Gamma", "Beta", "Alpha"]


def test_list_rows_unknown_sort_returns_400():
    with _people_db() as db:
        with pytest.raises(HTTPException) as exc:
            list_rows(
                "people",
                request=_request(),
                db=db,
                limit=50,
                offset=0,
                sort="not_a_column",
            )
    assert exc.value.status_code == 400
