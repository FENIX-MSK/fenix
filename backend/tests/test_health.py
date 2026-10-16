import pytest
from aiogram import Bot
from fastapi.testclient import TestClient

from fenix.config import BotMode, Settings
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


def test_api_starts_when_telegram_is_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    async def unreachable(*args: object, **kwargs: object) -> None:
        raise ConnectionError("telegram is blocked")

    monkeypatch.setattr(Bot, "set_webhook", unreachable)
    settings = Settings(
        telegram_bot_mode=BotMode.WEBHOOK,
        public_base_url="https://example.test",
        telegram_webhook_secret="secret",
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
