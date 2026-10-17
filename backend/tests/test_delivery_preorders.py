"""Epic 5: order parameters, delivery, preorders, pauses and kitchen load."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fakes import Worker, make_worker
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_orders import add_to_cart

from fenix.main import create_app
from fenix.modules.locations import api as locations
from fenix.modules.notifications.messages import guest_message, staff_new_order
from fenix.modules.ordering.kitchen import load_from, slots
from fenix.platform.config import Settings
from fenix.worker import release_due_preorders

ADDRESS = {"house": "2", "apartment": "15", "entrance": "1", "floor": "3", "comment": ""}


@pytest.fixture
def client(ready_guest: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


@pytest.fixture
def worker(ready_guest: async_sessionmaker[AsyncSession]) -> Worker:
    return make_worker(ready_guest)


def checkout(client: TestClient, headers: dict[str, str]) -> Any:
    return client.get("/api/v1/checkout", headers=headers).json()


def place_with(client: TestClient, headers: dict[str, str], **body: Any) -> Any:
    add_to_cart(client, headers, "Капучино")
    return client.post(
        "/api/v1/orders",
        headers=headers,
        json={"payment_method": "cash", "comment": "", **body},
    )


def params(client: TestClient, staff: dict[str, str]) -> Any:
    return client.get("/api/v1/staff/location/order-params", headers=staff).json()


def test_order_params_defaults_and_update(
    client: TestClient, staff_headers: dict[str, str], auth_headers: dict[str, str]
) -> None:
    current = params(client, staff_headers)
    assert current["prep_minutes"] == 20
    assert current["slot_step_minutes"] == 15
    assert current["unpaid_timeout_minutes"] == 15
    updated = current | {"prep_minutes": 30, "delivery_fee": 20000}
    response = client.put(
        "/api/v1/staff/location/order-params", headers=staff_headers, json=updated
    )
    assert response.status_code == 200
    assert checkout(client, auth_headers)["asap_minutes"] == 30
    assert checkout(client, auth_headers)["delivery_fee"] == 20000
    bad = current | {"slot_step_minutes": 7}
    rejected = client.put("/api/v1/staff/location/order-params", headers=staff_headers, json=bad)
    assert rejected.json()["error"]["code"] == "bad_params"
    guest = client.get("/api/v1/staff/location/order-params", headers=auth_headers)
    assert guest.status_code == 403


def test_delivery_order_with_fee_and_change(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    assert "delivery" in checkout(client, auth_headers)["fulfilment"]
    no_address = place_with(client, auth_headers, fulfilment="delivery")
    assert no_address.json()["error"]["code"] == "address_required"
    order = place_with(
        client, auth_headers, fulfilment="delivery", address=ADDRESS, change_from=500000
    ).json()
    assert order["fulfilment"] == "delivery"
    assert order["delivery_fee"] == 15000
    assert order["total"] == sum(line["total_price"] for line in order["lines"]) + 15000
    assert order["address"]["apartment"] == "15"
    assert order["change_from"] == 500000

    card = client.get(f"/api/v1/staff/orders/{order['id']}", headers=staff_headers).json()
    assert card["address"]["house"] == "2"
    small = place_with(
        client, auth_headers, fulfilment="delivery", address=ADDRESS, change_from=100
    )
    assert small.json()["error"]["code"] == "bad_change"
    card_payment = place_with(client, auth_headers, payment_method="card", change_from=500000)
    assert card_payment.json()["error"]["code"] == "bad_change"


def test_delivery_is_carried_to_the_door(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    order = place_with(client, auth_headers, fulfilment="delivery", address=ADDRESS).json()

    def act(current: Any, action: str, **body: Any) -> Any:
        return client.post(
            f"/api/v1/staff/orders/{order['id']}/actions",
            headers=staff_headers,
            json={"action": action, "expected_version": current["version"], **body},
        )

    current = order
    for action in ("accept", "start_cooking", "mark_ready"):
        current = act(current, action).json()
    assert act(current, "hand_over").json()["error"]["code"] == "transition_not_allowed"
    current = act(current, "dispatch").json()
    assert current["status"] == "delivering"
    assert act(current, "deliver").json()["error"]["code"] == "payment_required"
    current = act(current, "deliver", paid_with="cash").json()
    assert current["status"] == "delivered"

    pickup = place_with(client, auth_headers).json()
    for action in ("accept", "start_cooking", "mark_ready"):
        pickup = client.post(
            f"/api/v1/staff/orders/{pickup['id']}/actions",
            headers=staff_headers,
            json={"action": action, "expected_version": pickup["version"]},
        ).json()
    dispatched = client.post(
        f"/api/v1/staff/orders/{pickup['id']}/actions",
        headers=staff_headers,
        json={"action": "dispatch", "expected_version": pickup["version"]},
    )
    assert dispatched.json()["error"]["code"] == "transition_not_allowed"


async def test_delivery_messages(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str], worker: Worker
) -> None:
    order = place_with(
        client, auth_headers, fulfilment="delivery", address=ADDRESS, change_from=500000
    ).json()
    current = order
    for action in ("accept", "start_cooking", "mark_ready", "dispatch"):
        current = client.post(
            f"/api/v1/staff/orders/{order['id']}/actions",
            headers=staff_headers,
            json={"action": action, "expected_version": current["version"]},
        ).json()
    client.post(
        f"/api/v1/staff/orders/{order['id']}/actions",
        headers=staff_headers,
        json={"action": "deliver", "expected_version": current["version"], "paid_with": "cash"},
    ).raise_for_status()
    await worker.run()
    texts = [s.text for s in worker.gateway.sent if s.chat_id == "42"]
    assert "Доставка: корпус 2, кв. 15, подъезд 1, этаж 3." in texts[0]
    assert any("уже едет к вам" in t for t in texts)
    assert any("доставлен" in t for t in texts)


def test_delivery_pause_and_order_pause(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    client.put(
        "/api/v1/staff/location/pauses", headers=staff_headers, json={"delivery_paused": True}
    ).raise_for_status()
    state = checkout(client, auth_headers)
    assert state["fulfilment"] == ["pickup"]
    assert state["delivery_unavailable"] == "paused"
    blocked = place_with(client, auth_headers, fulfilment="delivery", address=ADDRESS)
    assert blocked.json()["error"]["code"] == "delivery_unavailable"
    assert place_with(client, auth_headers).status_code == 200

    paused = client.put(
        "/api/v1/staff/location/pauses", headers=staff_headers, json={"orders_paused": True}
    ).json()
    assert paused == {"orders_paused": True, "delivery_paused": True}
    assert checkout(client, auth_headers)["orders_paused"] is True
    assert client.get("/api/v1/location", headers=auth_headers).json()["orders_paused"] is True
    assert place_with(client, auth_headers).json()["error"]["code"] == "orders_paused"
    client.put(
        "/api/v1/staff/location/pauses",
        headers=staff_headers,
        json={"orders_paused": False, "delivery_paused": False},
    ).raise_for_status()
    assert place_with(client, auth_headers).status_code == 200


async def test_preorder_waits_and_is_released(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str], worker: Worker
) -> None:
    slots_now = checkout(client, auth_headers)["slots"]
    assert slots_now
    first = datetime.fromisoformat(slots_now[0])
    assert first - datetime.now(UTC) >= timedelta(minutes=20)
    assert first.minute % 15 == 0
    late = datetime.fromisoformat(slots_now[-1])
    order = place_with(client, auth_headers, scheduled_for=late.isoformat()).json()
    assert order["status"] == "scheduled"
    assert datetime.fromisoformat(order["scheduled_for"]) == late

    board = client.get("/api/v1/staff/orders", headers=staff_headers).json()
    assert next(o for o in board["orders"] if o["id"] == order["id"])["status"] == "scheduled"
    await worker.run()
    assert not [s for s in worker.gateway.sent if s.chat_id != "42"]  # not yet for the kitchen

    assert await release_due_preorders(worker.factory, datetime.now(UTC)) == (
        1 if late - datetime.now(UTC) <= timedelta(minutes=30) else 0
    )
    assert await release_due_preorders(worker.factory, late - timedelta(minutes=29)) in (0, 1)
    current = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers).json()
    assert current["status"] == "new"
    await worker.run()
    staff_texts = [s.text for s in worker.gateway.sent if s.chat_id != "42"]
    assert staff_texts == [] or staff_texts[0].startswith("Предзаказ к")


def test_stale_slot_is_refused_with_alternatives(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    soon = datetime.now(UTC) + timedelta(minutes=5)
    response = place_with(client, auth_headers, scheduled_for=soon.isoformat())
    error = response.json()["error"]
    assert error["code"] == "slot_unavailable"
    assert len(error["details"]["slots"]) >= 1


async def test_paid_preorder_is_scheduled(
    client: TestClient, auth_headers: dict[str, str], worker: Worker
) -> None:
    slot = checkout(client, auth_headers)["slots"][-1]
    order = place_with(client, auth_headers, payment_method="online", scheduled_for=slot).json()
    assert order["status"] == "pending_payment"
    client.post(
        f"/api/v1/payments/{order['payment_id']}/test-result",
        headers=auth_headers,
        json={"succeeded": True},
    ).raise_for_status()
    await worker.run()
    # The transition's own event is created after the first pass started.
    await worker.run(datetime.now(UTC) + timedelta(seconds=1))
    current = client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers).json()
    assert current["status"] == "scheduled"
    assert any("запланирован" in s.text for s in worker.gateway.sent)


def test_kitchen_load_levels_and_override(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    for _ in range(4):
        place_with(client, auth_headers).raise_for_status()
    board = client.get("/api/v1/staff/orders", headers=staff_headers).json()
    assert board["kitchen"] == {
        "level": "moderate",
        "in_work": 4,
        "wait_minutes": 30,
        "manual": False,
        "manual_until": None,
    }
    assert checkout(client, auth_headers)["asap_minutes"] == 30
    busy = client.post(
        "/api/v1/staff/orders/kitchen", headers=staff_headers, json={"level": "busy", "minutes": 30}
    ).json()
    assert busy["level"] == "busy" and busy["manual"] and busy["wait_minutes"] == 40
    location = client.get("/api/v1/location", headers=auth_headers).json()
    assert location["kitchen_busy"] is True and location["wait_minutes"] == 40
    # «Загружено» does not block ordering.
    assert place_with(client, auth_headers).status_code == 200
    auto = client.post(
        "/api/v1/staff/orders/kitchen", headers=staff_headers, json={"level": None}
    ).json()
    assert auto["manual"] is False and auto["level"] == "moderate"


async def test_manual_level_expires(seeded: async_sessionmaker[AsyncSession]) -> None:
    now = datetime.now(UTC)
    async with seeded() as session, session.begin():
        location_id = await locations.get_default_location_id(session)
        assert location_id
        await locations.set_kitchen_override(session, location_id, "busy", 30, now)
        during = await locations.get_order_settings(session, location_id, now)
        after = await locations.get_order_settings(
            session, location_id, now + timedelta(minutes=31)
        )
    assert during.kitchen_override is not None
    assert after.kitchen_override is None


def test_load_thresholds_are_pure() -> None:
    from fenix.modules.locations.hours import OpeningStatus

    settings = locations.OrderSettings(
        timezone="Europe/Moscow",
        prep_minutes=20,
        unpaid_timeout_minutes=15,
        status=OpeningStatus(True, "Открыто", None, None),
    )
    assert [load_from(n, settings).level for n in (0, 3, 4, 7, 8)] == [
        "calm",
        "calm",
        "moderate",
        "moderate",
        "busy",
    ]
    assert load_from(8, settings).wait_minutes == 40


def test_slots_follow_the_grid_until_closing() -> None:
    from zoneinfo import ZoneInfo

    from fenix.modules.locations.hours import OpeningStatus

    zone = ZoneInfo("Europe/Moscow")
    closes = datetime(2026, 10, 17, 22, 0, tzinfo=zone)
    settings = locations.OrderSettings(
        timezone="Europe/Moscow",
        prep_minutes=20,
        unpaid_timeout_minutes=15,
        status=OpeningStatus(True, "Открыто до 22:00", closes, None),
    )
    now = datetime(2026, 10, 17, 20, 52, tzinfo=zone)
    result = slots(settings, 20, now)
    assert [s.strftime("%H:%M") for s in result] == ["21:15", "21:30", "21:45", "22:00"]
    closed = locations.OrderSettings(
        timezone="Europe/Moscow",
        prep_minutes=20,
        unpaid_timeout_minutes=15,
        status=OpeningStatus(False, "Закрыто", None, None),
    )
    assert slots(closed, 20, now) == []


def test_messages_for_preorders_and_delivery() -> None:
    payload: dict[str, Any] = {
        "number": "#061",
        "status": "scheduled",
        "fulfilment": "delivery",
        "payment_method": "cash",
        "total": 150000,
        "timezone": "Europe/Moscow",
        "scheduled_for": "2026-10-17T16:30:00+00:00",
        "address": ADDRESS,
        "change_from": 500000,
        "comment": "",
        "lines": [{"title": "Пицца", "modifier_names": [], "quantity": 1}],
    }
    text = guest_message("placed", payload)
    assert text is not None and text.startswith("Заказ <b>#061</b> запланирован.")
    assert "Будет готов к 19:30." in text
    staff = staff_new_order(payload | {"status": "new"})
    assert staff.startswith("Предзаказ к 19:30 <b>#061</b> — доставка")
    assert "Сдача с 5 000 ₽" in staff
