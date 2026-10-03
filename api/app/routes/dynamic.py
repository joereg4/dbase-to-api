from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from sqlalchemy import types as satypes

from ..deps import get_db


router = APIRouter()

DBF_RECNO = "dbf_recno"
_RESERVED_ROW_PARAMS = frozenset({"limit", "offset", "sort"})
_FILTER_PREFIX = "filter."


def _table_column_names(db: Session, table: str) -> dict[str, satypes.TypeEngine] | None:
    """Return columns for a public table, or None if the table is absent."""
    insp = inspect(db.get_bind())
    if table not in insp.get_table_names(schema="public"):
        return None
    return {c["name"]: c["type"] for c in insp.get_columns(table, schema="public")}


def _require_table_columns(db: Session, table: str) -> dict[str, satypes.TypeEngine]:
    columns = _table_column_names(db, table)
    if columns is None:
        raise HTTPException(status_code=404, detail="Table not found")
    return columns


def _qualified_table(preparer, table: str) -> str:
    return f"{preparer.quote('public')}.{preparer.quote(table)}"


def stable_order_sql(column_names: list[str], preparer) -> str:
    """Prefer dbf_recno; otherwise order by every column for stable paging."""
    if DBF_RECNO in column_names:
        return preparer.quote(DBF_RECNO)
    if not column_names:
        return "1"
    return ", ".join(preparer.quote(c) for c in column_names)


def order_by_sql(column_names: list[str], preparer, sort: str | None) -> str:
    """Whitelist sort column; default to stable_order_sql. Tie-break with dbf_recno."""
    if not sort:
        return stable_order_sql(column_names, preparer)

    descending = sort.startswith("-")
    col = sort[1:] if descending else sort
    if col not in column_names:
        raise HTTPException(status_code=400, detail=f"Unknown sort column: {col}")

    direction = "DESC" if descending else "ASC"
    clause = f"{preparer.quote(col)} {direction}"
    if DBF_RECNO in column_names and col != DBF_RECNO:
        clause += f", {preparer.quote(DBF_RECNO)} ASC"
    return clause


def coerce_filter_value(coltype: satypes.TypeEngine, raw: str):
    """Parse a query string as the column type. Unparsable input is a 400."""
    try:
        return _coerce_filter_value(coltype, raw)
    except (ValueError, InvalidOperation, TypeError, ArithmeticError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid filter value: {raw!r}") from exc


def _coerce_filter_value(coltype: satypes.TypeEngine, raw: str):
    if isinstance(coltype, satypes.Boolean):
        lowered = raw.strip().lower()
        if lowered in {"true", "t", "1", "yes", "y"}:
            return True
        if lowered in {"false", "f", "0", "no", "n"}:
            return False
        raise ValueError(raw)
    # BigInteger and SmallInteger subclass Integer. Check them before Numeric.
    if isinstance(coltype, satypes.Integer):
        return int(raw)
    if isinstance(coltype, satypes.Numeric):
        return Decimal(raw)
    if isinstance(coltype, satypes.Float):
        return float(raw)
    # DateTime subclasses Date.
    if isinstance(coltype, satypes.DateTime):
        return datetime.fromisoformat(raw)
    if isinstance(coltype, satypes.Date):
        return date.fromisoformat(raw)
    return raw


def parse_equality_filters(
    query_params,
    columns: dict[str, satypes.TypeEngine],
    reserved: frozenset[str] = _RESERVED_ROW_PARAMS,
) -> dict:
    """Keep equality filters whose keys are real columns.

    ``limit``, ``offset``, and ``sort`` stay control parameters.
    A column with one of those names is filtered as ``filter.<column>``.
    """
    filters: dict = {}
    for key, value in query_params.items():
        if key.startswith(_FILTER_PREFIX):
            column = key[len(_FILTER_PREFIX) :]
        elif key in reserved:
            continue
        else:
            column = key
        if column not in columns:
            raise HTTPException(status_code=400, detail=f"Unknown filter column: {column}")
        filters[column] = coerce_filter_value(columns[column], value)
    return filters


def _where_clause(filters: dict, preparer) -> tuple[str, dict]:
    if not filters:
        return "", {}
    parts: list[str] = []
    params: dict = {}
    for i, (col, value) in enumerate(filters.items()):
        params[f"f{i}"] = value
        parts.append(f"{preparer.quote(col)} = :f{i}")
    return " WHERE " + " AND ".join(parts), params


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


@router.get("/tables/{table}/rows/{dbf_recno}")
def get_row(table: str, dbf_recno: int, db: Session = Depends(get_db)) -> dict:
    columns = _require_table_columns(db, table)
    if DBF_RECNO not in columns:
        raise HTTPException(
            status_code=404,
            detail="Table has no dbf_recno column; re-import to enable row lookup",
        )

    bind = db.get_bind()
    preparer = bind.dialect.identifier_preparer
    qualified = _qualified_table(preparer, table)
    stmt = text(f"SELECT * FROM {qualified} WHERE {preparer.quote(DBF_RECNO)} = :recno LIMIT 1")
    row = db.execute(stmt, {"recno": dbf_recno}).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Row not found")
    return dict(row)


@router.get("/tables/{table}/rows")
def list_rows(
    table: str,
    request: Request,
    db: Session = Depends(get_db),
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort: Annotated[str | None, Query()] = None,
) -> dict:
    columns = _require_table_columns(db, table)
    column_names = list(columns)

    # Identifiers cannot be bound as parameters. The dialect preparer escapes
    # embedded double-quotes so a hostile name cannot break out of the literal.
    bind = db.get_bind()
    preparer = bind.dialect.identifier_preparer
    qualified = _qualified_table(preparer, table)
    filters = parse_equality_filters(request.query_params, columns)
    where_sql, filter_params = _where_clause(filters, preparer)
    order_by = order_by_sql(column_names, preparer, sort)

    count = db.execute(
        text(f"SELECT COUNT(*) FROM {qualified}{where_sql}"), filter_params
    ).scalar_one()
    rows = (
        db.execute(
            text(
                f"SELECT * FROM {qualified}{where_sql} "
                f"ORDER BY {order_by} LIMIT :limit OFFSET :offset"
            ),
            {**filter_params, "limit": limit, "offset": offset},
        )
        .mappings()
        .all()
    )
    return {
        "items": [dict(r) for r in rows],
        "limit": limit,
        "offset": offset,
        "count": count,
    }
