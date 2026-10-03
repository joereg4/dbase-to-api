from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text

from ..deps import get_db


router = APIRouter()

DBF_RECNO = "dbf_recno"


def _table_column_names(db: Session, table: str) -> list[str] | None:
    """Return column names for a public table, or None if the table is absent."""
    bind = db.get_bind()
    insp = inspect(bind)
    schema = "public" if bind.dialect.name == "postgresql" else None
    if table not in insp.get_table_names(schema=schema):
        return None
    return [c["name"] for c in insp.get_columns(table, schema=schema)]


def stable_order_sql(column_names: list[str], preparer) -> str:
    """Prefer dbf_recno; otherwise order by every column for stable paging."""
    if DBF_RECNO in column_names:
        return preparer.quote(DBF_RECNO)
    if not column_names:
        return "1"
    return ", ".join(preparer.quote(c) for c in column_names)


@router.get("/tables")
def list_tables(db: Session = Depends(get_db)) -> list[str]:
    sql = text(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    rows = db.execute(sql).scalars().all()
    return rows


@router.get("/tables/{table}/columns")
def list_columns(table: str, db: Session = Depends(get_db)) -> list[dict]:
    # Validate table existence in 'public'
    exists_sql = text(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema='public' AND table_name=:t
        """
    )
    if not db.execute(exists_sql, {"t": table}).first():
        raise HTTPException(status_code=404, detail="Table not found")

    sql = text(
        """
        SELECT column_name AS name, data_type AS type
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=:t
        ORDER BY ordinal_position
        """
    )
    return [dict(r) for r in db.execute(sql, {"t": table}).mappings().all()]


@router.get("/tables/{table}/rows")
def list_rows(
    table: str,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    column_names = _table_column_names(db, table)
    if column_names is None:
        raise HTTPException(status_code=404, detail="Table not found")

    # Identifiers cannot be bound as parameters. The dialect preparer escapes
    # embedded double-quotes so a hostile name cannot break out of the literal.
    bind = db.get_bind()
    preparer = bind.dialect.identifier_preparer
    if bind.dialect.name == "postgresql":
        qualified = f"{preparer.quote('public')}.{preparer.quote(table)}"
    else:
        qualified = preparer.quote(table)
    order_by = stable_order_sql(column_names, preparer)
    stmt = text(f"SELECT * FROM {qualified} ORDER BY {order_by} LIMIT :limit OFFSET :offset")
    rows = db.execute(stmt, {"limit": limit, "offset": offset}).mappings().all()
    return [dict(r) for r in rows]
