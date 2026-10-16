import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.main import create_app
from fenix.modules.catalog.models import StopListEntry
from fenix.platform.config import Settings


@pytest.fixture
def client(seeded: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


def view(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    body: dict[str, Any] = client.get("/api/v1/staff/stop-list", headers=headers).json()
    return body


def stop(client: TestClient, headers: dict[str, str], **body: Any) -> Any:
    payload = {k: str(v) if isinstance(v, uuid.UUID) else v for k, v in body.items()}
    return client.put("/api/v1/staff/stop-list", headers=headers, json=payload)


def guest_dish(client: TestClient, headers: dict[str, str], name: str) -> dict[str, Any]:
    menu = client.get("/api/v1/menu", headers=headers).json()
    found: dict[str, Any] = next(
        d for c in menu["categories"] for d in c["dishes"] if d["name"] == name
    )
    return found


def test_sizes_off_and_back(
    client: TestClient, staff_headers: dict[str, str], auth_headers: dict[str, str]
) -> None:
    fries = next(d for d in view(client, staff_headers)["dishes"] if d["name"] == "Картофель фри")
    small, large = fries["sizes"]
    assert stop(client, staff_headers, size_id=small["id"], stopped=True).status_code == 200
    dish = guest_dish(client, auth_headers, "Картофель фри")
    assert (dish["sold_out"], dish["price_from"]) == (False, 19900)

    stop(client, staff_headers, size_id=large["id"], stopped=True)
    assert guest_dish(client, auth_headers, "Картофель фри")["sold_out"] is True
    assert [
        s["stopped"]
        for s in next(
            d for d in view(client, staff_headers)["dishes"] if d["name"] == "Картофель фри"
        )["sizes"]
    ] == [True, True]

    stop(client, staff_headers, size_id=small["id"], stopped=False)
    stop(client, staff_headers, size_id=large["id"], stopped=False)
    assert guest_dish(client, auth_headers, "Картофель фри")["sold_out"] is False


async def test_repeat_is_idempotent(
    client: TestClient, staff_headers: dict[str, str], seeded: async_sessionmaker[AsyncSession]
) -> None:
    syrup = next(
        m
        for g in view(client, staff_headers)["groups"]
        for m in g["modifiers"]
        if m["name"] == "Сироп"
    )
    stop(client, staff_headers, modifier_id=syrup["id"], stopped=True)
    stop(client, staff_headers, modifier_id=syrup["id"], stopped=True)
    async with seeded() as session:
        assert (
            await session.execute(select(func.count()).select_from(StopListEntry))
        ).scalar_one() == 1


def test_stopped_modifier_is_unavailable_to_guests(
    client: TestClient, staff_headers: dict[str, str], auth_headers: dict[str, str]
) -> None:
    syrup = next(
        m
        for g in view(client, staff_headers)["groups"]
        for m in g["modifiers"]
        if m["name"] == "Сироп"
    )
    stop(client, staff_headers, modifier_id=syrup["id"], stopped=True)
    espresso = guest_dish(client, auth_headers, "Эспрессо")
    card = client.get(f"/api/v1/menu/dishes/{espresso['id']}", headers=auth_headers).json()
    assert (
        next(m for m in card["groups"][0]["modifiers"] if m["name"] == "Сироп")["available"]
        is False
    )


@pytest.mark.parametrize(
    "body", [{"stopped": True}, {"size_id": "x", "modifier_id": "y", "stopped": True}]
)
def test_bad_target(
    client: TestClient, staff_headers: dict[str, str], body: dict[str, Any]
) -> None:
    view_body = view(client, staff_headers)
    resolved = {
        k: (
            view_body["dishes"][0]["sizes"][0]["id"]
            if v == "x"
            else view_body["groups"][0]["modifiers"][0]["id"]
            if v == "y"
            else v
        )
        for k, v in body.items()
    }
    response = stop(client, staff_headers, **resolved)
    assert (response.status_code, response.json()["error"]["code"]) == (422, "bad_target")


def test_unknown_size(client: TestClient, staff_headers: dict[str, str]) -> None:
    response = stop(client, staff_headers, size_id=uuid.uuid4(), stopped=True)
    assert (response.status_code, response.json()["error"]["code"]) == (404, "size_not_found")


def test_hidden_dishes_are_listed_and_marked(
    client: TestClient, staff_headers: dict[str, str]
) -> None:
    cola = next(d for d in view(client, staff_headers)["dishes"] if d["name"] == "Кола")
    catalog = client.get("/api/v1/staff/catalog", headers=staff_headers).json()["categories"]
    full = next(d for c in catalog for d in c["dishes"] if d["name"] == "Кола")
    client.put(
        f"/api/v1/staff/dishes/{cola['id']}",
        headers=staff_headers,
        json={
            "category_id": full["category_id"],
            "name": "Кола",
            "is_hidden": True,
            "sizes": full["sizes"],
        },
    )
    assert (
        next(d for d in view(client, staff_headers)["dishes"] if d["name"] == "Кола")["is_hidden"]
        is True
    )


def test_guest_cannot_use_stop_list(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.get("/api/v1/staff/stop-list", headers=auth_headers).status_code == 403
