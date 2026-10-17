"""Stories 4.1 and 4.2: the guest's order history and «Повторить»."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from init_data import sign_init_data
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_orders import add_to_cart, place

from fenix.main import create_app
from fenix.platform.config import Settings


@pytest.fixture
def client(ready_guest: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


def order(client: TestClient, headers: dict[str, str], name: str = "Капучино") -> Any:
    add_to_cart(client, headers, name)
    response = place(client, headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_history_is_newest_first_and_paged(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    placed = [order(client, auth_headers)["number"] for _ in range(5)]
    first = client.get("/api/v1/orders?limit=2", headers=auth_headers).json()
    assert [o["number"] for o in first["orders"]] == placed[::-1][:2]
    assert first["next_cursor"]
    seen = [o["number"] for o in first["orders"]]
    cursor = first["next_cursor"]
    while cursor:
        page = client.get(f"/api/v1/orders?limit=2&cursor={cursor}", headers=auth_headers).json()
        seen += [o["number"] for o in page["orders"]]
        cursor = page["next_cursor"]
    assert seen == placed[::-1]
    card = first["orders"][0]
    assert card["lines"][0]["title"].startswith("Капучино")
    assert card["total"] > 0 and card["status"] == "new" and card["created_at"]


def test_history_shows_only_own_orders(client: TestClient, auth_headers: dict[str, str]) -> None:
    order(client, auth_headers)
    stranger = {"Authorization": f"tma {sign_init_data({'id': 7, 'first_name': 'Чужой'})}"}
    assert client.get("/api/v1/orders", headers=stranger).json() == {
        "orders": [],
        "next_cursor": None,
    }


def test_bad_cursor(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/orders?cursor=zzz", headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "bad_cursor"


def test_active_order_banner(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    assert client.get("/api/v1/orders/active", headers=auth_headers).json() is None
    placed = order(client, auth_headers)
    active = client.get("/api/v1/orders/active", headers=auth_headers).json()
    assert active["id"] == placed["id"]
    client.post(
        f"/api/v1/staff/orders/{placed['id']}/actions",
        headers=staff_headers,
        json={"action": "cancel", "expected_version": placed["version"], "note": "тест"},
    ).raise_for_status()
    assert client.get("/api/v1/orders/active", headers=auth_headers).json() is None


def test_repeat_puts_lines_back_at_todays_prices(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    add_to_cart(client, auth_headers, "Капучино", 2)
    add_to_cart(client, auth_headers, "Филадельфия")
    placed = place(client, auth_headers).json()
    assert client.get("/api/v1/cart", headers=auth_headers).json()["lines"] == []

    repeated = client.post(f"/api/v1/orders/{placed['id']}/repeat", headers=auth_headers).json()
    assert repeated["added"] == 2
    assert repeated["skipped"] == []
    lines = repeated["cart"]["lines"]
    assert sorted((line["title"].split(" ·")[0], line["quantity"]) for line in lines) == [
        ("Капучино", 2),
        ("Филадельфия", 1),
    ]
    assert repeated["cart"]["total"] == placed["total"]


def test_repeat_skips_stopped_lines(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    add_to_cart(client, auth_headers, "Капучино")
    add_to_cart(client, auth_headers, "Филадельфия")
    placed = place(client, auth_headers).json()
    stop_list = client.get("/api/v1/staff/stop-list", headers=staff_headers).json()
    roll = next(d for d in stop_list["dishes"] if d["name"] == "Филадельфия")
    for size in roll["sizes"]:
        client.put(
            "/api/v1/staff/stop-list",
            headers=staff_headers,
            json={"size_id": size["id"], "stopped": True},
        ).raise_for_status()

    repeated = client.post(f"/api/v1/orders/{placed['id']}/repeat", headers=auth_headers).json()
    assert repeated["added"] == 1
    assert repeated["skipped"] == ["Филадельфия"]
    assert len(repeated["cart"]["lines"]) == 1


def test_cannot_repeat_someone_elses_order(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    placed = order(client, auth_headers)
    stranger = {"Authorization": f"tma {sign_init_data({'id': 7, 'first_name': 'Чужой'})}"}
    response = client.post(f"/api/v1/orders/{placed['id']}/repeat", headers=stranger)
    assert response.status_code == 404
