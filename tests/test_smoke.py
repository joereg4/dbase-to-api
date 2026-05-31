from unittest.mock import patch

from fastapi.testclient import TestClient


def test_health_endpoint_importable():
    from api.app.main import app

    client = TestClient(app)
    with patch("api.app.db.check_database", return_value=True):
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"
