"""Story 7.2: Grafana alerts reach the bound alert chat through the outbox."""

from collections.abc import Iterator

import pytest
from fakes import make_worker
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_staff_chat import STAFF, Chat, GroupMessage

from fenix.main import create_app
from fenix.platform.config import Settings
from fenix.telegram.handlers.staff_chat import ALERTS_BOUND, NOT_STAFF, handle_alerts

TOKEN = "alert-token"
GRAFANA = {
    "alerts": [
        {
            "status": "firing",
            "labels": {"alertname": "API недоступен"},
            "annotations": {"summary": "api не отвечает > 2 мин"},
        },
        {"status": "resolved", "labels": {"alertname": "Outbox"}, "annotations": {}},
    ]
}


@pytest.fixture
def client(seeded: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(alerts_webhook_token=TOKEN))) as client:  # type: ignore[call-arg, arg-type]
        yield client


def test_webhook_needs_the_token(client: TestClient) -> None:
    assert client.post("/api/internal/alerts", json=GRAFANA).status_code == 401
    wrong = {"Authorization": "Bearer nope"}
    assert client.post("/api/internal/alerts", json=GRAFANA, headers=wrong).status_code == 401


async def test_alerts_go_to_the_bound_chat(
    client: TestClient, seeded: async_sessionmaker[AsyncSession], staff_headers: dict[str, str]
) -> None:
    guest = GroupMessage(chat=Chat(id=-900, title="Алерты"))
    await handle_alerts(guest, seeded)  # type: ignore[arg-type]
    assert guest.answers[0][0] == NOT_STAFF
    message = GroupMessage(from_user=STAFF, chat=Chat(id=-900, title="Алерты"))
    await handle_alerts(message, seeded)  # type: ignore[arg-type]
    assert message.answers[0][0] == ALERTS_BOUND

    response = client.post(
        "/api/internal/alerts", json=GRAFANA, headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert response.json() == {"queued": 2}
    worker = make_worker(seeded)
    await worker.run()
    [sent] = worker.gateway.sent
    assert sent.chat_id == "-900"
    assert sent.text == ("🔴 <b>API недоступен</b> — api не отвечает &gt; 2 мин\n✅ <b>Outbox</b>")
