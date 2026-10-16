from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.main import create_app
from fenix.platform.config import Settings


@pytest.fixture
def client(seeded: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


@pytest.fixture
def staff(client: TestClient, staff_headers: dict[str, str]) -> Any:
    def call(method: str, path: str, body: Any = None) -> Any:
        return client.request(method, f"/api/v1/staff{path}", headers=staff_headers, json=body)

    return call


def catalog(staff: Any) -> list[dict[str, Any]]:
    categories: list[dict[str, Any]] = staff("GET", "/catalog").json()["categories"]
    return categories


def find_dish(staff: Any, name: str) -> dict[str, Any]:
    return next(d for c in catalog(staff) for d in c["dishes"] if d["name"] == name)


def find_category(staff: Any, name: str) -> dict[str, Any]:
    return next(c for c in catalog(staff) if c["name"] == name)


def guest_groups(client: TestClient, headers: dict[str, str], dish_id: str) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = client.get(
        f"/api/v1/menu/dishes/{dish_id}", headers=headers
    ).json()["groups"]
    return groups


SAUCE = {
    "name": "Соус к фри",
    "min_choice": 0,
    "max_choice": 1,
    "options": [{"name": "Кетчуп", "price_delta": 3000}, {"name": "Сырный", "price_delta": 4000}],
}


def test_seeded_groups_are_listed(staff: Any) -> None:
    groups = {g["name"]: g for g in staff("GET", "/modifier-groups").json()}
    assert set(groups) == {"Соус", "Котлета", "Добавки"}
    assert len(groups["Котлета"]["dish_ids"]) == 3
    assert groups["Добавки"]["category_ids"] == [find_category(staff, "Кофе")["id"]]


@pytest.mark.parametrize(
    ("patch", "code"),
    [
        ({"min_choice": 2, "max_choice": 1}, "choice_bounds"),
        ({"max_choice": 3}, "choice_bounds"),
        ({"options": []}, "group_needs_option"),
        ({"options": [{"name": "Сироп"}, {"name": "Сироп"}]}, "duplicate_option_name"),
    ],
)
def test_validation(staff: Any, patch: dict[str, Any], code: str) -> None:
    response = staff("POST", "/modifier-groups", SAUCE | patch)
    assert (response.status_code, response.json()["error"]["code"]) == (422, code)


def test_group_on_a_category_reaches_every_dish(
    staff: Any, client: TestClient, auth_headers: dict[str, str]
) -> None:
    group_id = staff("POST", "/modifier-groups", SAUCE).json()["id"]
    snacks = find_category(staff, "Закуски")
    assert (
        staff(
            "PUT", f"/modifier-groups/{group_id}/links", {"category_ids": [snacks["id"]]}
        ).status_code
        == 200
    )
    for dish in snacks["dishes"]:
        assert "Соус к фри" in [g["name"] for g in guest_groups(client, auth_headers, dish["id"])]


def test_dish_and_category_link_show_the_group_once(
    staff: Any, client: TestClient, auth_headers: dict[str, str]
) -> None:
    addons = next(g for g in staff("GET", "/modifier-groups").json() if g["name"] == "Добавки")
    cappuccino = find_dish(staff, "Капучино")
    staff(
        "PUT",
        f"/modifier-groups/{addons['id']}/links",
        {"dish_ids": [cappuccino["id"]], "category_ids": addons["category_ids"]},
    )
    names = [g["name"] for g in guest_groups(client, auth_headers, cappuccino["id"])]
    assert names == ["Добавки"]


def test_new_option_price_is_used(
    staff: Any, client: TestClient, auth_headers: dict[str, str]
) -> None:
    addons = next(g for g in staff("GET", "/modifier-groups").json() if g["name"] == "Добавки")
    options = [o | {} for o in addons["options"]]
    options[0]["price_delta"] = 5000
    body = {"name": "Добавки", "min_choice": 0, "max_choice": 2, "options": options}
    assert staff("PUT", f"/modifier-groups/{addons['id']}", body).status_code == 200
    espresso = find_dish(staff, "Эспрессо")
    price = client.post(
        "/api/v1/menu/price",
        headers=auth_headers,
        json={
            "dish_id": espresso["id"],
            "size_id": espresso["sizes"][0]["id"],
            "modifier_ids": [options[0]["id"]],
            "quantity": 1,
        },
    ).json()
    assert price["total_price"] == 12000 + 5000


def test_delete_group_removes_it_from_dishes(
    staff: Any, client: TestClient, auth_headers: dict[str, str]
) -> None:
    wings = find_dish(staff, "Куриные крылышки в соусе")
    sauce = next(g for g in staff("GET", "/modifier-groups").json() if g["name"] == "Соус")
    assert staff("DELETE", f"/modifier-groups/{sauce['id']}").status_code == 200
    assert guest_groups(client, auth_headers, wings["id"]) == []


def test_unknown_link_is_rejected(staff: Any) -> None:
    group_id = staff("POST", "/modifier-groups", SAUCE).json()["id"]
    response = staff(
        "PUT",
        f"/modifier-groups/{group_id}/links",
        {"dish_ids": ["00000000-0000-0000-0000-000000000000"]},
    )
    assert response.json()["error"]["code"] == "unknown_link"
