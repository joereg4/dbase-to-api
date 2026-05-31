from unittest.mock import patch

from fastapi.testclient import TestClient


def test_health_ok_when_db_responds():
    from api.app.main import app

    client = TestClient(app)
    with patch("api.app.db.check_database", return_value=True):
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_health_503_when_db_unavailable():
    from api.app.main import app

    client = TestClient(app)
    with patch("api.app.db.check_database", return_value=False):
        r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["status"] == "degraded"
    assert r.json()["database"] == "unavailable"
