from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..deps import get_db


router = APIRouter()


@router.get("")
def list_customers(db: Session = Depends(get_db)) -> list[dict]:
    return []


@router.get("/sample-people")
def list_sample_people(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    rows = db.execute(
        text(
            "SELECT id, name, active FROM sample_people ORDER BY id LIMIT :limit OFFSET :offset"
        ),
        {"limit": limit, "offset": offset},
    ).mappings().all()
    return [dict(r) for r in rows]


@router.get("/sample-people/{id}")
def get_sample_person(id: int, db: Session = Depends(get_db)) -> dict:
    row = db.execute(
        text("SELECT id, name, active FROM sample_people WHERE id = :id"),
        {"id": id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return dict(row)

