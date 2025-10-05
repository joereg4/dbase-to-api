from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..deps import get_db


router = APIRouter()


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
    # Validate table
    exists_sql = text(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='public' AND table_name=:t
        """
    )
    if not db.execute(exists_sql, {"t": table}).first():
        raise HTTPException(status_code=404, detail="Table not found")

    # Build a safe statement: identifiers cannot be bound; we whitelist by checking existence above
    stmt = text(f'SELECT * FROM public."{table}" LIMIT :limit OFFSET :offset')
    rows = db.execute(stmt, {"limit": limit, "offset": offset}).mappings().all()
    return [dict(r) for r in rows]
