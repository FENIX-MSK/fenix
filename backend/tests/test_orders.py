import asyncio
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.main import create_app
from fenix.modules.identity.models import IdentityUser
from fenix.modules.locations.models import Location
from fenix.modules.ordering import api as ordering
from fenix.modules.ordering.models import Order
from fenix.modules.ordering.orders import TRANSITIONS, Actor, next_number
from fenix.platform.config import Settings


@pytest.fixture
def client(ready_guest: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


def add_to_cart(client: TestClient, headers: dict[str, str], name: str, quantity: int = 1) -> None:
    menu = client.get("/api/v1/menu", headers=headers).json()
    dish = next(d for c in menu["categories"] for d in c["dishes"] if d["name"] == name)
    card = client.get(f"/api/v1/menu/dishes/{dish['id']}", headers=headers).json()
    client.post(
        "/api/v1/cart/items",
        headers=headers,
        json={
            "dish_id": dish["id"],
            "size_id": card["sizes"][0]["id"],
            "modifier_ids": [],
            "quantity": quantity,
        },
    ).raise_for_status()


def place(client: TestClient, headers: dict[str, str], method: str = "cash") -> Any:
    return client.post(
        "/api/v1/orders", headers=headers, json={"payment_method": method, "comment": "без лука"}
    )


def test_cash_order(client: TestClient, auth_headers: dict[str, str]) -> None:
    add_to_cart(client, auth_headers, "Филадельфия", 2)
    response = place(client, auth_headers)
    assert response.status_code == 200
    order = response.json()
    assert (order["number"], order["status"], order["payment_status"], order["version"]) == (
        "#001",
        "new",
        "unpaid",
        1,
    )
    assert order["total"] == 2 * 69900
    assert order["lines"] == [
        {
            "title": "Филадельфия",
            "modifier_names": [],
            "quantity": 2,
            "unit_price": 69900,
            "total_price": 139800,
            "original_unit_price": 69900,
            "promotion_title": None,
        }
    ]
    assert client.get("/api/v1/cart", headers=auth_headers).json()["lines"] == []
    assert (
        client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers).json()["number"] == "#001"
    )

    add_to_cart(client, auth_headers, "Кола")
    assert place(client, auth_headers).json()["number"] == "#002"


def test_online_order_waits_for_payment(client: TestClient, auth_headers: dict[str, str]) -> None:
    add_to_cart(client, auth_headers, "Кола")
    assert place(client, auth_headers, "online").json()["status"] == "pending_payment"


def error(response: Any) -> str:
    code: str = response.json()["error"]["code"]
    return code


def test_empty_cart(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert error(place(client, auth_headers)) == "empty_cart"


async def test_unavailable_line(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    add_to_cart(client, auth_headers, "Кола")
    stop = client.get("/api/v1/staff/stop-list", headers=staff_headers).json()
    size = next(d for d in stop["dishes"] if d["name"] == "Кола")["sizes"][0]["id"]
    client.put(
        "/api/v1/staff/stop-list", headers=staff_headers, json={"size_id": size, "stopped": True}
    )
    assert error(place(client, auth_headers)) == "cart_has_unavailable"


async def test_closed_location(
    client: TestClient, auth_headers: dict[str, str], ready_guest: async_sessionmaker[AsyncSession]
) -> None:
    add_to_cart(client, auth_headers, "Кола")
    async with ready_guest() as session, session.begin():
        (await session.execute(select(Location))).scalar_one().opening_hours = []
    response = place(client, auth_headers)
    assert (response.status_code, error(response)) == (422, "location_closed")


async def test_contact_required(
    client: TestClient, auth_headers: dict[str, str], ready_guest: async_sessionmaker[AsyncSession]
) -> None:
    add_to_cart(client, auth_headers, "Кола")
    async with ready_guest() as session, session.begin():
        await session.execute(update(IdentityUser).values(phone=None))
    assert error(place(client, auth_headers)) == "contact_required"


def test_other_guests_order_is_hidden(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    add_to_cart(client, auth_headers, "Кола")
    order_id = place(client, auth_headers).json()["id"]
    assert client.get(f"/api/v1/orders/{order_id}", headers=staff_headers).status_code == 404


async def test_numbers_are_unique_under_concurrency(
    ready_guest: async_sessionmaker[AsyncSession],
) -> None:
    async with ready_guest() as session:
        location_id = (await session.execute(select(Location.id))).scalar_one()
    day = datetime.now(UTC).date()

    async def take() -> int:
        async with ready_guest() as session, session.begin():
            return await next_number(session, location_id, day)

    numbers = await asyncio.gather(*(take() for _ in range(20)))
    assert sorted(numbers) == list(range(1, 21))


async def test_number_restarts_next_business_day(
    ready_guest: async_sessionmaker[AsyncSession],
) -> None:
    async with ready_guest() as session, session.begin():
        location_id = (await session.execute(select(Location.id))).scalar_one()
        today = datetime(2026, 10, 17).date()
        assert [await next_number(session, location_id, today) for _ in range(3)] == [1, 2, 3]
        assert await next_number(session, location_id, today + timedelta(days=1)) == 1


# ---- the transition table (AD-3), covered completely ----

STATUSES = [
    "pending_payment",
    "scheduled",
    "new",
    "accepted",
    "cooking",
    "ready",
    "handed_over",
    "delivering",
    "delivered",
    "cancelled",
]
ACTIONS = sorted({action for _, action in TRANSITIONS})
ACTORS = ["guest", "staff", "system"]


async def order_in(
    factory: async_sessionmaker[AsyncSession],
    client: TestClient,
    headers: dict[str, str],
    status: str,
    fulfilment: str = "pickup",
) -> uuid.UUID:
    add_to_cart(client, headers, "Кола")
    order_id = uuid.UUID(place(client, headers).json()["id"])
    async with factory() as session, session.begin():
        await session.execute(
            update(Order).where(Order.id == order_id).values(status=status, fulfilment=fulfilment)
        )
    return order_id


@pytest.mark.parametrize("status", STATUSES)
async def test_every_transition_of(
    status: str,
    client: TestClient,
    auth_headers: dict[str, str],
    ready_guest: async_sessionmaker[AsyncSession],
) -> None:
    for action in ACTIONS:
        for actor in ACTORS:
            for fulfilment in ("pickup", "delivery"):
                order_id = await order_in(ready_guest, client, auth_headers, status, fulfilment)
                rule = TRANSITIONS.get((status, action))
                allowed = (
                    rule is not None
                    and actor in rule.actors
                    and rule.fulfilment in (None, fulfilment)
                )
                async with ready_guest() as session, session.begin():
                    try:
                        result = await ordering.transition(
                            session,
                            order_id,
                            action,
                            Actor(actor),  # type: ignore[arg-type]
                            expected_version=1,
                            now=datetime.now(UTC),
                            note="нет продуктов" if action == "cancel" else None,
                        )
                    except ordering.OrderError as exc:
                        assert not allowed, (
                            f"{status} --{action}/{actor}/{fulfilment}--> rejected: {exc.code}"
                        )
                        assert exc.code == "transition_not_allowed"
                    else:
                        assert allowed, (
                            f"{status} --{action}/{actor}/{fulfilment}--> should be rejected"
                        )
                        assert rule is not None
                        assert (result.status, result.version) == (rule.to, 2)
                        assert result.log[-1].action == action


async def test_stale_version_is_a_conflict(
    client: TestClient, auth_headers: dict[str, str], ready_guest: async_sessionmaker[AsyncSession]
) -> None:
    order_id = await order_in(ready_guest, client, auth_headers, "new")
    staff = Actor("staff")
    now = datetime.now(UTC)
    async with ready_guest() as session, session.begin():
        await ordering.transition(
            session, order_id, "accept", staff, expected_version=1, now=now, ready_at=now
        )
    async with ready_guest() as session, session.begin():
        with pytest.raises(ordering.OrderError) as conflict:
            await ordering.transition(
                session, order_id, "cancel", staff, expected_version=1, now=now, note="x"
            )
    assert (conflict.value.code, conflict.value.status) == ("order_conflict", 409)


async def test_staff_cancel_needs_a_reason(
    client: TestClient, auth_headers: dict[str, str], ready_guest: async_sessionmaker[AsyncSession]
) -> None:
    order_id = await order_in(ready_guest, client, auth_headers, "new")
    async with ready_guest() as session, session.begin():
        with pytest.raises(ordering.OrderError) as missing:
            await ordering.transition(
                session,
                order_id,
                "cancel",
                Actor("staff"),
                expected_version=1,
                now=datetime.now(UTC),
                note="  ",
            )
    assert missing.value.code == "reason_required"
