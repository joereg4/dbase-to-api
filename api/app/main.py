from fastapi import FastAPI

from .routes import customers, invoices, vendors


app = FastAPI(title="dbase-to-api", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(customers.router, prefix="/customers", tags=["customers"])
app.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
app.include_router(vendors.router, prefix="/vendors", tags=["vendors"])

