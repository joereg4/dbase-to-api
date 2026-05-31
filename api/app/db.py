import logging

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from .config import settings

log = logging.getLogger("api.db")
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def check_database() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        log.exception("database health check failed")
        return False
