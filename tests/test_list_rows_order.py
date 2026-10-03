"""list_rows orders by dbf_recno so page contents stay stable."""

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.orm import sessionmaker

from api.app.routes.dynamic import list_rows, stable_order_sql


def _sqlite_preparer():
    return create_engine("sqlite:///:memory:").dialect.identifier_preparer


def test_stable_order_sql_prefers_dbf_recno():
    preparer = _sqlite_preparer()
    assert stable_order_sql(["id", "name", "dbf_recno"], preparer) == preparer.quote("dbf_recno")


def test_stable_order_sql_falls_back_to_all_columns():
    preparer = _sqlite_preparer()
    assert stable_order_sql(["id", "name"], preparer) == (
        f"{preparer.quote('id')}, {preparer.quote('name')}"
    )


def test_list_rows_orders_by_dbf_recno_despite_insert_order():
    engine = create_engine("sqlite:///:memory:")
    people = Table(
        "people",
        MetaData(),
        Column("name", String(20)),
        Column("dbf_recno", Integer, primary_key=True),
    )
    people.create(engine)
    with engine.begin() as conn:
        # Insert out of source order so heap order would put Beta first.
        conn.execute(people.insert(), [{"name": "Beta", "dbf_recno": 2}])
        conn.execute(people.insert(), [{"name": "Alpha", "dbf_recno": 1}])

    db = sessionmaker(bind=engine)()
    try:
        rows = list_rows("people", db=db, limit=50, offset=0)
    finally:
        db.close()

    assert [r["dbf_recno"] for r in rows] == [1, 2]
    assert [r["name"] for r in rows] == ["Alpha", "Beta"]
