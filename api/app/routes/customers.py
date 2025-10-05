from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db


router = APIRouter()


@router.get("")
def list_customers(db: Session = Depends(get_db)) -> list[dict]:
    # Placeholder; will query real table post-import
    return []

