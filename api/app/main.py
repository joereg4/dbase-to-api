from fastapi import FastAPI

from .routes import dynamic


app = FastAPI(title="dbase-to-api", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(dynamic.router, prefix="/db", tags=["dynamic"])
