from fastapi.testclient import TestClient

from fenix.main import create_app
from fenix.platform.config import Settings


def test_health() -> None:
    app = create_app(Settings())
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metrics_stay_outside_the_versioned_api() -> None:
    with TestClient(create_app(Settings())) as client:
        response = client.get("/metrics")
    assert response.status_code == 200


def test_telegram_webhook_is_gone() -> None:
    with TestClient(create_app(Settings())) as client:
        response = client.post("/telegram/webhook", json={"update_id": 1})
    assert response.status_code == 404
