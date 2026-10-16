from fastapi.testclient import TestClient

from fenix.config import Settings
from fenix.main import create_app


def test_health() -> None:
    app = create_app(Settings())
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_webhook_rejects_missing_secret() -> None:
    app = create_app(Settings())
    with TestClient(app) as client:
        response = client.post("/telegram/webhook", json={"update_id": 1})
    assert response.status_code == 401
