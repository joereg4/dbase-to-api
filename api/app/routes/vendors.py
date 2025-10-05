from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db


router = APIRouter()


@router.get("")
def list_vendors(db: Session = Depends(get_db)) -> list[dict]:
    return []

