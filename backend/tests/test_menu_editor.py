from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.main import create_app
from fenix.modules.catalog.models import DishSize, StopListEntry
from fenix.modules.locations.models import Location
from fenix.platform.config import Settings


@pytest.fixture
def client(seeded: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


class Editor:
    def __init__(self, client: TestClient, headers: dict[str, str]) -> None:
        self.client, self.headers = client, headers

    def call(self, method: str, path: str, body: Any = None) -> Any:
        return self.client.request(method, f"/api/v1/staff{path}", headers=self.headers, json=body)

    def catalog(self) -> list[dict[str, Any]]:
        categories: list[dict[str, Any]] = self.call("GET", "/catalog").json()["categories"]
        return categories

    def category(self, name: str) -> dict[str, Any]:
        return next(c for c in self.catalog() if c["name"] == name)

    def dish(self, name: str) -> dict[str, Any]:
        return next(d for c in self.catalog() for d in c["dishes"] if d["name"] == name)


@pytest.fixture
def editor(client: TestClient, staff_headers: dict[str, str]) -> Editor:
    return Editor(client, staff_headers)


def guest_menu(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    body: dict[str, Any] = client.get("/api/v1/menu", headers=headers).json()
    return body


def guest_dish_names(client: TestClient, headers: dict[str, str]) -> list[str]:
    return [d["name"] for c in guest_menu(client, headers)["categories"] for d in c["dishes"]]


def error(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def test_new_category_goes_last_and_hidden_one_disappears(
    editor: Editor, client: TestClient, auth_headers: dict[str, str]
) -> None:
    created = editor.call("POST", "/categories", {"name": "  Супы  ", "description": "в горшочке"})
    assert created.status_code == 200
    assert editor.catalog()[-1]["name"] == "Супы"
    assert guest_menu(client, auth_headers)["categories"][-1]["name"] == "Супы"

    category_id = created.json()["id"]
    editor.call("PUT", f"/categories/{category_id}", {"name": "Супы", "is_hidden": True})
    assert "Супы" not in [c["name"] for c in guest_menu(client, auth_headers)["categories"]]
    assert editor.category("Супы")["is_hidden"] is True


def test_dish_lifecycle(editor: Editor, client: TestClient, auth_headers: dict[str, str]) -> None:
    desserts = editor.category("Десерты")
    body = {
        "category_id": desserts["id"],
        "name": "Чизкейк",
        "description": "сливочный сыр, печенье",
        "portion": "120 г",
        "sizes": [{"price": 34900}],
    }
    dish_id = editor.call("POST", "/dishes", body).json()["id"]
    assert editor.category("Десерты")["dishes"][-1]["name"] == "Чизкейк"
    assert "Чизкейк" in guest_dish_names(client, auth_headers)

    size_id = editor.dish("Чизкейк")["sizes"][0]["id"]
    body["sizes"] = [{"id": size_id, "price": 37900}]
    assert editor.call("PUT", f"/dishes/{dish_id}", body).status_code == 200
    price = client.post(
        "/api/v1/menu/price",
        headers=auth_headers,
        json={"dish_id": dish_id, "size_id": size_id, "modifier_ids": [], "quantity": 1},
    ).json()
    assert price["total_price"] == 37900

    assert editor.call("DELETE", f"/dishes/{dish_id}").status_code == 200
    assert "Чизкейк" not in guest_dish_names(client, auth_headers)


@pytest.mark.parametrize(
    ("sizes", "code"),
    [
        ([], "dish_needs_size"),
        ([{"name": "M", "price": 100}, {"name": "", "price": 200}], "size_name_required"),
        (
            [{"name": "400 мл", "price": 100}, {"name": "400 мл", "price": 200}],
            "duplicate_size_name",
        ),
    ],
)
def test_size_rules(editor: Editor, sizes: list[dict[str, Any]], code: str) -> None:
    category = editor.category("Кофе")
    response = editor.call(
        "POST", "/dishes", {"category_id": category["id"], "name": "Новое", "sizes": sizes}
    )
    assert error(response) == (422, code)


def test_foreign_size_is_rejected(editor: Editor) -> None:
    cappuccino, fries = editor.dish("Капучино"), editor.dish("Картофель фри")
    body = {
        "category_id": cappuccino["category_id"],
        "name": "Капучино",
        "sizes": [{"id": fries["sizes"][0]["id"], "name": "250 мл", "price": 1}],
    }
    assert error(editor.call("PUT", f"/dishes/{cappuccino['id']}", body)) == (422, "foreign_size")


async def test_removed_size_takes_its_stop_list_entry(
    editor: Editor, seeded: async_sessionmaker[AsyncSession]
) -> None:
    cappuccino = editor.dish("Капучино")
    small, large = cappuccino["sizes"]
    async with seeded() as session, session.begin():
        location_id = (await session.execute(select(Location.id))).scalar_one()
        session.add(StopListEntry(location_id=location_id, dish_size_id=small["id"]))
    body = {
        "category_id": cappuccino["category_id"],
        "name": "Капучино",
        "sizes": [{"id": large["id"], "name": "", "price": large["price"], "portion": "400 мл"}],
    }
    assert editor.call("PUT", f"/dishes/{cappuccino['id']}", body).status_code == 200
    async with seeded() as session:
        assert (await session.execute(select(StopListEntry))).first() is None
        sizes = (
            (await session.execute(select(DishSize.id).where(DishSize.dish_id == cappuccino["id"])))
            .scalars()
            .all()
        )
    assert [str(s) for s in sizes] == [large["id"]]


def test_move_dish_to_another_category(editor: Editor) -> None:
    cola = editor.dish("Кола")
    desserts = editor.category("Десерты")
    body = {
        "category_id": desserts["id"],
        "name": "Кола",
        "portion": "330 мл",
        "sizes": [cola["sizes"][0]],
    }
    assert editor.call("PUT", f"/dishes/{cola['id']}", body).status_code == 200
    assert editor.category("Десерты")["dishes"][-1]["name"] == "Кола"


def test_reorder(editor: Editor, client: TestClient, auth_headers: dict[str, str]) -> None:
    ids = [c["id"] for c in editor.catalog()]
    assert editor.call("POST", "/categories/order", {"ids": list(reversed(ids))}).status_code == 200
    assert guest_menu(client, auth_headers)["categories"][0]["name"] == "Десерты"
    assert error(editor.call("POST", "/categories/order", {"ids": ids[:-1]})) == (422, "bad_order")

    drinks = editor.category("Напитки")
    dish_ids = [d["id"] for d in drinks["dishes"]]
    editor.call("POST", "/dishes/order", {"category_id": drinks["id"], "ids": dish_ids[::-1]})
    assert editor.category("Напитки")["dishes"][0]["name"] == "Ред Булл"


def test_delete_category_only_when_empty(editor: Editor) -> None:
    assert error(editor.call("DELETE", f"/categories/{editor.category('Кофе')['id']}")) == (
        409,
        "category_not_empty",
    )
    empty = editor.call("POST", "/categories", {"name": "Пусто"}).json()["id"]
    assert editor.call("DELETE", f"/categories/{empty}").status_code == 200


def test_name_is_required(editor: Editor) -> None:
    assert error(editor.call("POST", "/categories", {"name": "   "})) == (422, "name_required")


def test_guest_cannot_edit(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.get("/api/v1/staff/catalog", headers=auth_headers).status_code == 403
    assert (
        client.post(
            "/api/v1/staff/categories", headers=auth_headers, json={"name": "X"}
        ).status_code
        == 403
    )
