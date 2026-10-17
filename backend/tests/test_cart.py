from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from init_data import sign_init_data
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.main import create_app
from fenix.platform.config import Settings


@pytest.fixture
def client(seeded: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


class Guest:
    def __init__(self, client: TestClient, headers: dict[str, str]) -> None:
        self.client, self.headers = client, headers

    def menu_dish(self, name: str) -> dict[str, Any]:
        menu = self.client.get("/api/v1/menu", headers=self.headers).json()
        dish = next(d for c in menu["categories"] for d in c["dishes"] if d["name"] == name)
        card: dict[str, Any] = self.client.get(
            f"/api/v1/menu/dishes/{dish['id']}", headers=self.headers
        ).json()
        return card

    def add(
        self,
        dish: dict[str, Any],
        size: str = "",
        modifiers: tuple[str, ...] = (),
        quantity: int = 1,
    ) -> Any:
        modifier_ids = [
            m["id"] for g in dish["groups"] for m in g["modifiers"] if m["name"] in modifiers
        ]
        size_id = next(s["id"] for s in dish["sizes"] if s["name"] == size)
        return self.client.post(
            "/api/v1/cart/items",
            headers=self.headers,
            json={
                "dish_id": dish["id"],
                "size_id": size_id,
                "modifier_ids": modifier_ids,
                "quantity": quantity,
            },
        )

    def cart(self) -> dict[str, Any]:
        body: dict[str, Any] = self.client.get("/api/v1/cart", headers=self.headers).json()
        return body


@pytest.fixture
def guest(client: TestClient, auth_headers: dict[str, str]) -> Guest:
    return Guest(client, auth_headers)


def test_add_and_merge(guest: Guest) -> None:
    cappuccino = guest.menu_dish("Капучино")
    assert guest.add(cappuccino, "400 мл", ("Сироп",), 2).status_code == 200
    cart = guest.cart()
    [line] = cart["lines"]
    assert (line["title"], line["modifier_names"], line["quantity"]) == (
        "Капучино · 400 мл",
        ["Сироп"],
        2,
    )
    assert (line["unit_price"], line["total_price"], cart["total"], cart["count"]) == (
        28000,
        56000,
        56000,
        2,
    )

    guest.add(cappuccino, "400 мл", ("Сироп",), 1)
    assert [ln["quantity"] for ln in guest.cart()["lines"]] == [3]
    guest.add(cappuccino, "250 мл")
    assert len(guest.cart()["lines"]) == 2


def test_incomplete_and_invalid(guest: Guest) -> None:
    wings = guest.menu_dish("Куриные крылышки в соусе")
    response = guest.add(wings)
    assert (response.status_code, response.json()["error"]["code"]) == (422, "incomplete_selection")
    cappuccino = guest.menu_dish("Капучино")
    bbq = next(m["id"] for g in wings["groups"] for m in g["modifiers"] if m["name"] == "BBQ")
    response = guest.client.post(
        "/api/v1/cart/items",
        headers=guest.headers,
        json={
            "dish_id": cappuccino["id"],
            "size_id": cappuccino["sizes"][0]["id"],
            "modifier_ids": [bbq],
            "quantity": 1,
        },
    )
    assert response.json()["error"] == {
        "code": "invalid_selection",
        "message": "The cart change was rejected",
        "details": {"reason": "foreign_modifier"},
    }


def test_quantity_and_remove(guest: Guest) -> None:
    guest.add(guest.menu_dish("Филадельфия"))
    line_id = guest.cart()["lines"][0]["id"]
    patched = guest.client.patch(
        f"/api/v1/cart/items/{line_id}", headers=guest.headers, json={"quantity": 5}
    )
    assert (patched.json()["lines"][0]["quantity"], patched.json()["total"]) == (5, 5 * 69900)
    emptied = guest.client.patch(
        f"/api/v1/cart/items/{line_id}", headers=guest.headers, json={"quantity": 0}
    )
    assert emptied.json() == {"lines": [], "total": 0, "count": 0}
    guest.add(guest.menu_dish("Филадельфия"))
    line_id = guest.cart()["lines"][0]["id"]
    assert (
        guest.client.delete(f"/api/v1/cart/items/{line_id}", headers=guest.headers).json()["lines"]
        == []
    )


def test_stop_list_marks_line_and_excludes_it(guest: Guest, staff_headers: dict[str, str]) -> None:
    fries = guest.menu_dish("Картофель фри")
    guest.add(fries, "М", quantity=2)
    guest.add(guest.menu_dish("Филадельфия"))
    small = next(s["id"] for s in fries["sizes"] if s["name"] == "М")
    guest.client.put(
        "/api/v1/staff/stop-list", headers=staff_headers, json={"size_id": small, "stopped": True}
    )
    cart = guest.cart()
    fries_line = next(ln for ln in cart["lines"] if ln["title"].startswith("Картофель"))
    assert (fries_line["available"], fries_line["problem"], fries_line["total_price"]) == (
        False,
        "unavailable",
        None,
    )
    assert (cart["total"], cart["count"]) == (69900, 1)


def test_new_price_is_used(guest: Guest, staff_headers: dict[str, str]) -> None:
    philadelphia = guest.menu_dish("Филадельфия")
    guest.add(philadelphia)
    catalog = guest.client.get("/api/v1/staff/catalog", headers=staff_headers).json()["categories"]
    full = next(d for c in catalog for d in c["dishes"] if d["name"] == "Филадельфия")
    full["sizes"][0]["price"] = 75000
    guest.client.put(
        f"/api/v1/staff/dishes/{full['id']}",
        headers=staff_headers,
        json={
            k: full[k]
            for k in ("category_id", "name", "description", "portion", "is_hidden", "sizes")
        },
    )
    assert guest.cart()["total"] == 75000


def test_deleted_dish_keeps_its_name(guest: Guest, staff_headers: dict[str, str]) -> None:
    guest.add(guest.menu_dish("Кола"))
    cola = guest.menu_dish("Кола")
    guest.client.delete(f"/api/v1/staff/dishes/{cola['id']}", headers=staff_headers)
    [line] = guest.cart()["lines"]
    assert (line["title"], line["available"]) == ("Кола", False)


def test_cart_is_per_user_and_shared_across_devices(guest: Guest, client: TestClient) -> None:
    guest.add(guest.menu_dish("Филадельфия"))
    other = {"Authorization": f"tma {sign_init_data({'id': 99, 'first_name': 'Олег'})}"}
    assert client.get("/api/v1/cart", headers=other).json()["lines"] == []
    line_id = guest.cart()["lines"][0]["id"]
    response = client.delete(f"/api/v1/cart/items/{line_id}", headers=other)
    assert (response.status_code, response.json()["error"]["code"]) == (404, "cart_item_not_found")
    # Same account, a second "device": fresh launch data, same cart.
    again = {"Authorization": f"tma {sign_init_data()}"}
    assert len(client.get("/api/v1/cart", headers=again).json()["lines"]) == 1
