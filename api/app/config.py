import os
from pydantic import BaseModel


class Settings(BaseModel):
    database_url: str = (
        os.getenv("DATABASE_URL") or "postgresql+psycopg://postgres:postgres@db:5432/dbase"
    )


settings = Settings()
