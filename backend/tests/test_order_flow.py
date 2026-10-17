"""Stories 3.4-3.9 end to end: guest, outbox worker, payments, staff board."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fakes import Worker, make_worker
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_orders import add_to_cart, place

from fenix.main import create_app
from fenix.modules.notifications import api as notifications
from fenix.modules.ordering.models import Order
from fenix.modules.payments.models import Payment
from fenix.platform.config import Settings
from fenix.platform.outbox import OutboxEvent
from fenix.worker import cancel_overdue_unpaid


@pytest.fixture
def client(ready_guest: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


@pytest.fixture
def worker(ready_guest: async_sessionmaker[AsyncSession]) -> Worker:
    return make_worker(ready_guest)


@pytest.fixture
async def staff_chat(ready_guest: async_sessionmaker[AsyncSession]) -> None:
    from fenix.modules.locations import api as locations

    async with ready_guest() as session, session.begin():
        location_id = await locations.get_default_location_id(session)
        assert location_id
        await notifications.bind_staff_chat(
            session,
            location_id,
            platform="telegram",
            chat_id="-100500",
            title="Кухня",
            user_id=None,
        )


def order_with(client: TestClient, headers: dict[str, str], method: str = "cash") -> Any:
    add_to_cart(client, headers, "Капучино", 2)
    response = place(client, headers, method)
    assert response.status_code == 200, response.text
    return response.json()


def act(
    client: TestClient, headers: dict[str, str], order: dict[str, Any], action: str, **body: Any
) -> Any:
    return client.post(
        f"/api/v1/staff/orders/{order['id']}/actions",
        headers=headers,
        json={"action": action, "expected_version": order["version"], **body},
    )


async def event_names(factory: async_sessionmaker[AsyncSession]) -> list[str]:
    async with factory() as session:
        rows = await session.execute(select(OutboxEvent.name).order_by(OutboxEvent.created_at))
        return list(rows.scalars())


async def test_cash_order_is_announced_to_guest_and_staff(
    client: TestClient,
    auth_headers: dict[str, str],
    worker: Worker,
    staff_chat: None,
) -> None:
    order = order_with(client, auth_headers)
    assert await event_names(worker.factory) == ["ordering.order.placed"]
    await worker.run()

    guest, staff = sorted(worker.gateway.sent, key=lambda s: s.chat_id != "42")
    assert guest.chat_id == "42"
    assert f"Заказ <b>{order['number']}</b> оформлен" in guest.text
    assert "Капучино" in guest.text and "× 2" in guest.text
    assert guest.buttons and guest.buttons[0].web_app_url == f"https://app.test?order={order['id']}"
    assert staff.chat_id == "-100500"
    assert staff.text.startswith(f"Новый заказ <b>{order['number']}</b> — самовывоз")
    assert "без лука" in staff.text
    assert staff.buttons and staff.buttons[0].url == (
        f"https://t.me/fenix_test_bot?start=order_{order['id']}"
    )
    channels = {channel for channel, _ in worker.redis.published}
    assert f"order:{order['id']}" in channels
    assert any(c.startswith("staff:") for c in channels)
    # Delivered once: a second pass sends nothing more.
    await worker.run()
    assert len(worker.gateway.sent) == 2


async def test_telegram_outage_is_retried_without_blocking_the_order(
    client: TestClient, auth_headers: dict[str, str], worker: Worker
) -> None:
    worker.gateway.failures = [RuntimeError("telegram unreachable")]
    order = order_with(client, auth_headers)
    now = datetime.now(UTC)
    await worker.run(now)
    assert worker.gateway.sent == []
    assert (
        client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers).json()["status"] == "new"
    )
    await worker.run(now + timedelta(seconds=5))
    assert [s.chat_id for s in worker.gateway.sent] == ["42"]


async def test_blocked_bot_drops_the_message(
    client: TestClient, auth_headers: dict[str, str], worker: Worker
) -> None:
    worker.gateway.failures = [notifications.Undeliverable("bot was blocked by the user")]
    order_with(client, auth_headers)
    await worker.run()
    async with worker.factory() as session:
        event = (await session.execute(select(OutboxEvent))).scalar_one()
    assert event.processed_at is not None


async def test_online_payment_moves_the_order_to_the_kitchen_once(
    client: TestClient, auth_headers: dict[str, str], worker: Worker, staff_chat: None
) -> None:
    order = order_with(client, auth_headers, "online")
    assert order["status"] == "pending_payment"
    assert order["payment_status"] == "pending"
    payment_id = order["payment_id"]
    await worker.run()
    assert worker.gateway.sent == []  # nothing to say until it is paid

    paid = client.post(
        f"/api/v1/payments/{payment_id}/test-result", headers=auth_headers, json={"succeeded": True}
    )
    assert paid.json()["payment_status"] == "paid"
    # The provider repeats its notification: still one payment, one transition.
    again = client.post(
        f"/api/v1/payments/{payment_id}/test-result", headers=auth_headers, json={"succeeded": True}
    )
    assert again.status_code == 200
    await worker.run()
    await worker.run()

    current = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers).json()
    assert current["status"] == "new"
    assert current["payment_status"] == "paid"
    names = await event_names(worker.factory)
    assert names.count("payments.payment.succeeded") == 1
    assert names.count("ordering.order.payment_confirmed") == 1
    texts = [s.text for s in worker.gateway.sent]
    assert any(t.startswith("Оплата прошла. Заказ") for t in texts)
    assert any(t.startswith("Новый заказ") for t in texts)


async def test_failed_payment_can_be_retried(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    order = order_with(client, auth_headers, "online")
    failed = client.post(
        f"/api/v1/payments/{order['payment_id']}/test-result",
        headers=auth_headers,
        json={"succeeded": False},
    ).json()
    assert failed["payment_status"] == "failed"
    assert failed["payment_id"] is None
    retried = client.post(f"/api/v1/orders/{order['id']}/payments", headers=auth_headers).json()
    assert retried["payment_status"] == "pending"
    assert retried["payment_id"] not in (None, order["payment_id"])
    # The first attempt is closed and cannot be paid any more.
    late = client.post(
        f"/api/v1/payments/{order['payment_id']}/test-result",
        headers=auth_headers,
        json={"succeeded": True},
    )
    assert late.status_code == 200 and late.json()["payment_status"] == "pending"


async def test_someone_elses_payment_is_hidden(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    from init_data import sign_init_data

    order = order_with(client, auth_headers, "online")
    stranger = {"Authorization": f"tma {sign_init_data({'id': 7, 'first_name': 'Чужой'})}"}
    response = client.post(
        f"/api/v1/payments/{order['payment_id']}/test-result",
        headers=stranger,
        json={"succeeded": True},
    )
    assert response.status_code == 404


async def test_unpaid_order_is_cancelled_after_the_timeout(
    client: TestClient, auth_headers: dict[str, str], worker: Worker
) -> None:
    order = order_with(client, auth_headers, "online")
    now = datetime.now(UTC)
    assert await cancel_overdue_unpaid(worker.factory, now + timedelta(minutes=14)) == 0
    assert await cancel_overdue_unpaid(worker.factory, now + timedelta(minutes=16)) == 1
    current = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers).json()
    assert current["status"] == "cancelled"
    # The guest can no longer pay the cancelled order.
    late = client.post(
        f"/api/v1/payments/{order['payment_id']}/test-result",
        headers=auth_headers,
        json={"succeeded": True},
    )
    assert late.status_code == 409
    assert late.json()["error"]["code"] == "payment_cancelled"
    await worker.run()
    assert worker.gateway.sent[-1].text.endswith("отменён: оплата не поступила вовремя.")


async def test_staff_handles_the_order_through_the_board(
    client: TestClient,
    auth_headers: dict[str, str],
    staff_headers: dict[str, str],
    worker: Worker,
) -> None:
    order = order_with(client, auth_headers)
    board = client.get("/api/v1/staff/orders", headers=staff_headers).json()
    card = next(o for o in board["orders"] if o["id"] == order["id"])
    assert card["customer_phone"] == "+79991234567"
    assert card["payment_status"] == "unpaid"
    assert card["lines"][0]["title"].startswith("Капучино")

    accepted = act(client, staff_headers, card, "accept")
    assert accepted.status_code == 200, accepted.text
    accepted_card = accepted.json()
    ready_at = datetime.fromisoformat(accepted_card["ready_at"])
    assert timedelta(minutes=19) < ready_at - datetime.now(UTC) <= timedelta(minutes=20)

    # A second tap from a stale screen loses (AD-3).
    stale = act(client, staff_headers, card, "cancel", note="передумали")
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "order_conflict"

    cooking = act(client, staff_headers, accepted_card, "start_cooking").json()
    ready = act(client, staff_headers, cooking, "mark_ready").json()
    unpaid = act(client, staff_headers, ready, "hand_over")
    assert unpaid.status_code == 422
    assert unpaid.json()["error"]["code"] == "payment_required"
    handed = act(client, staff_headers, ready, "hand_over", paid_with="card").json()
    assert handed["status"] == "handed_over"
    assert handed["payment_status"] == "paid"
    assert handed["paid_with"] == "card"
    assert [e["action"] for e in handed["log"]] == [
        "create",
        "accept",
        "start_cooking",
        "mark_ready",
        "hand_over",
    ]
    assert handed["log"][1]["actor_name"] == "Света"
    # Not on the board any more.
    board = client.get("/api/v1/staff/orders", headers=staff_headers).json()
    assert all(o["id"] != order["id"] for o in board["orders"])

    await worker.run()
    texts = [s.text for s in worker.gateway.sent if s.chat_id == "42"]
    assert any("Будет готов к" in t for t in texts)
    assert any("готов — можно забирать" in t for t in texts)


async def test_custom_ready_time_and_paid_before_hand_over(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    order = order_with(client, auth_headers)
    at = (datetime.now(UTC) + timedelta(minutes=45)).replace(microsecond=0)
    accepted = act(client, staff_headers, order, "accept", ready_at=at.isoformat()).json()
    assert datetime.fromisoformat(accepted["ready_at"]) == at
    paid = client.post(
        f"/api/v1/staff/orders/{order['id']}/payment",
        headers=staff_headers,
        json={"method": "cash"},
    ).json()
    assert paid["paid_with"] == "cash"
    twice = client.post(
        f"/api/v1/staff/orders/{order['id']}/payment",
        headers=staff_headers,
        json={"method": "card"},
    )
    assert twice.status_code == 409


async def test_guest_cannot_use_the_board(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.get("/api/v1/staff/orders", headers=auth_headers).status_code == 403


async def test_cancel_needs_a_reason_and_hides_it_from_the_guest(
    client: TestClient,
    auth_headers: dict[str, str],
    staff_headers: dict[str, str],
    worker: Worker,
) -> None:
    order = order_with(client, auth_headers)
    assert act(client, staff_headers, order, "cancel").json()["error"]["code"] == "reason_required"
    cancelled = act(client, staff_headers, order, "cancel", note="нет молока").json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancel_reason"] == "нет молока"
    guest_view = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers).json()
    assert "cancel_reason" not in guest_view
    await worker.run()
    last = [s.text for s in worker.gateway.sent if s.chat_id == "42"][-1]
    assert last.endswith("отменён.")
    assert "молока" not in last


async def test_cancelled_online_order_is_refunded(
    client: TestClient,
    auth_headers: dict[str, str],
    staff_headers: dict[str, str],
    worker: Worker,
) -> None:
    order = order_with(client, auth_headers, "online")
    client.post(
        f"/api/v1/payments/{order['payment_id']}/test-result",
        headers=auth_headers,
        json={"succeeded": True},
    )
    await worker.run()
    current = client.get(f"/api/v1/staff/orders/{order['id']}", headers=staff_headers).json()
    cancelled = act(client, staff_headers, current, "cancel", note="закончился кофе").json()
    assert cancelled["status"] == "cancelled"
    await worker.run()
    refunded = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers).json()
    assert refunded["payment_status"] == "refunded"
    last = [s.text for s in worker.gateway.sent if s.chat_id == "42"][-1]
    assert "Деньги вернутся" in last and "кофе" not in last
    async with worker.factory() as session:
        statuses = (await session.execute(select(Payment.status))).scalars().all()
    assert statuses == ["refunded"]


async def test_payment_event_for_a_settled_order_is_a_no_op(
    client: TestClient, auth_headers: dict[str, str], worker: Worker
) -> None:
    from fenix.platform import outbox

    order = order_with(client, auth_headers)
    async with worker.factory() as session, session.begin():
        outbox.emit(
            session,
            "payments.payment.succeeded",
            {"order_id": order["id"], "location_id": str(uuid.uuid4()), "payment_id": "x"},
        )
    await worker.run()
    async with worker.factory() as session:
        status = (
            await session.execute(select(Order.status).where(Order.id == uuid.UUID(order["id"])))
        ).scalar_one()
        failed = (
            (await session.execute(select(OutboxEvent).where(OutboxEvent.processed_at.is_(None))))
            .scalars()
            .all()
        )
    assert status == "new"
    assert failed == []


async def test_old_unpaid_without_payment_rows_still_cancels(
    client: TestClient, auth_headers: dict[str, str], worker: Worker
) -> None:
    order = order_with(client, auth_headers, "online")
    async with worker.factory() as session, session.begin():
        await session.execute(
            update(Order)
            .where(Order.id == uuid.UUID(order["id"]))
            .values(created_at=datetime.now(UTC) - timedelta(hours=1))
        )
    assert await cancel_overdue_unpaid(worker.factory, datetime.now(UTC)) == 1
