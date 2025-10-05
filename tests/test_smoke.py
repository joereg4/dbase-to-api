from fastapi.testclient import TestClient


def test_health_endpoint_importable():
    # Import the FastAPI app
    from api.app.main import app

    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"

