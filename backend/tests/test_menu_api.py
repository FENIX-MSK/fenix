import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.main import create_app
from fenix.modules.catalog import api as catalog
from fenix.modules.catalog.models import Category, Dish, DishSize, StopListEntry
from fenix.modules.locations import api as locations
from fenix.modules.locations.models import Location
from fenix.platform.config import Settings


@pytest.fixture
async def seeded(
    session_factory: async_sessionmaker[AsyncSession],
) -> async_sessionmaker[AsyncSession]:
    async with session_factory() as session, session.begin():
        await locations.seed_defaults(session)
        await catalog.seed_menu(session)
    return session_factory


@pytest.fixture
def client(seeded: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


def menu(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    response = client.get("/api/v1/menu", headers=headers)
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def find(body: dict[str, Any], name: str) -> dict[str, Any]:
    for category in body["categories"]:
        for dish in category["dishes"]:
            if dish["name"] == name:
                return dish  # type: ignore[no-any-return]
    raise AssertionError(f"{name} not in menu")


async def stop(
    factory: async_sessionmaker[AsyncSession],
    dish: str,
    size: str,
    location_id: uuid.UUID | None = None,
) -> None:
    async with factory() as session, session.begin():
        size_id = (
            await session.execute(
                select(DishSize.id).join(Dish).where(Dish.name == dish, DishSize.name == size)
            )
        ).scalar_one()
        if location_id is None:
            location_id = (await session.execute(select(Location.id))).scalar_one()
        session.add(StopListEntry(location_id=location_id, dish_size_id=size_id))


def test_menu_in_print_order(client: TestClient, auth_headers: dict[str, str]) -> None:
    body = menu(client, auth_headers)
    assert [c["name"] for c in body["categories"]] == [
        "Роллы",
        "Сеты",
        "Пицца",
        "Закуски",
        "Лепёшки",
        "Бургеры",
        "Кофе",
        "Лимонады",
        "Напитки",
        "Десерты",
    ]
    assert body["categories"][0]["dishes"][0]["name"] == "Жареный ролл с креветкой"
    assert body["categories"][2]["description"] == "32 см"
    assert sum(len(c["dishes"]) for c in body["categories"]) == 70


def test_single_size_dish(client: TestClient, auth_headers: dict[str, str]) -> None:
    dish = find(menu(client, auth_headers), "Филадельфия")
    assert dish | {"id": None} == {
        "id": None,
        "name": "Филадельфия",
        "description": "рис, лосось, нори, огурец, творожный сыр",
        "portion": "170 г",
        "price_from": 69900,
        "has_sizes": False,
        "sold_out": False,
        "photo_url": None,
    }


def test_sized_dish_price_from(client: TestClient, auth_headers: dict[str, str]) -> None:
    fries = find(menu(client, auth_headers), "Картофель фри")
    assert (fries["price_from"], fries["has_sizes"], fries["sold_out"]) == (12900, True, False)
    assert find(menu(client, auth_headers), "Капучино")["portion"] == "250 мл"


async def test_partly_stopped_dish_prices_from_what_is_left(
    client: TestClient, seeded: async_sessionmaker[AsyncSession], auth_headers: dict[str, str]
) -> None:
    await stop(seeded, "Капучино", "250 мл")
    cappuccino = find(menu(client, auth_headers), "Капучино")
    assert (cappuccino["price_from"], cappuccino["sold_out"]) == (25000, False)


async def test_fully_stopped_dish_is_sold_out(
    client: TestClient, seeded: async_sessionmaker[AsyncSession], auth_headers: dict[str, str]
) -> None:
    await stop(seeded, "Картофель фри", "М")
    await stop(seeded, "Картофель фри", "Б")
    fries = find(menu(client, auth_headers), "Картофель фри")
    assert (fries["sold_out"], fries["price_from"]) == (True, 12900)


async def test_other_locations_stop_list_does_not_apply(
    client: TestClient, seeded: async_sessionmaker[AsyncSession], auth_headers: dict[str, str]
) -> None:
    async with seeded() as session, session.begin():
        other = Location(name="Другая точка", address="—", phone="—")
        session.add(other)
        await session.flush()
        other_id = other.id
    await stop(seeded, "Филадельфия", "", other_id)
    assert find(menu(client, auth_headers), "Филадельфия")["sold_out"] is False


async def test_hidden_dish_and_category_are_not_shown(
    client: TestClient, seeded: async_sessionmaker[AsyncSession], auth_headers: dict[str, str]
) -> None:
    async with seeded() as session, session.begin():
        await session.execute(update(Dish).where(Dish.name == "Кола").values(is_hidden=True))
        await session.execute(
            update(Category).where(Category.name == "Десерты").values(is_hidden=True)
        )
    body = menu(client, auth_headers)
    assert "Десерты" not in [c["name"] for c in body["categories"]]
    with pytest.raises(AssertionError):
        find(body, "Кола")


async def test_category_with_only_hidden_dishes_is_empty(
    client: TestClient, seeded: async_sessionmaker[AsyncSession], auth_headers: dict[str, str]
) -> None:
    async with seeded() as session, session.begin():
        lepeshki = (
            await session.execute(select(Category.id).where(Category.name == "Лепёшки"))
        ).scalar_one()
        await session.execute(
            update(Dish).where(Dish.category_id == lepeshki).values(is_hidden=True)
        )
    category = next(c for c in menu(client, auth_headers)["categories"] if c["name"] == "Лепёшки")
    assert category["dishes"] == []


def test_menu_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/menu").status_code == 401
