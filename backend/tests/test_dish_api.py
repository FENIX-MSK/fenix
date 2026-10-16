import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.main import create_app
from fenix.modules.catalog.models import Dish, DishSize, Modifier, StopListEntry
from fenix.modules.locations.models import Location
from fenix.platform.config import Settings


@pytest.fixture
def client(seeded: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


@pytest.fixture
def api(client: TestClient, auth_headers: dict[str, str]) -> Api:
    return Api(client, auth_headers)


class Api:
    def __init__(self, client: TestClient, headers: dict[str, str]) -> None:
        self.client, self.headers = client, headers

    def dish(self, dish_id: uuid.UUID) -> Any:
        return self.client.get(f"/api/v1/menu/dishes/{dish_id}", headers=self.headers)

    def price(self, **body: Any) -> Any:
        payload = {
            key: str(value) if isinstance(value, uuid.UUID) else value
            for key, value in body.items()
        }
        if "modifier_ids" in payload:
            payload["modifier_ids"] = [str(m) for m in payload["modifier_ids"]]
        return self.client.post("/api/v1/menu/price", headers=self.headers, json=payload)


async def ids(factory: async_sessionmaker[AsyncSession], dish: str) -> dict[str, Any]:
    async with factory() as session:
        dish_row = (await session.execute(select(Dish).where(Dish.name == dish))).scalar_one()
        sizes = (
            (
                await session.execute(
                    select(DishSize)
                    .where(DishSize.dish_id == dish_row.id)
                    .order_by(DishSize.position)
                )
            )
            .scalars()
            .all()
        )
        return {"dish": dish_row.id, "sizes": {s.name: s.id for s in sizes}}


async def modifier(factory: async_sessionmaker[AsyncSession], name: str) -> uuid.UUID:
    async with factory() as session:
        return (
            await session.execute(select(Modifier.id).where(Modifier.name == name))
        ).scalar_one()


async def stop(factory: async_sessionmaker[AsyncSession], **target: uuid.UUID) -> None:
    async with factory() as session, session.begin():
        location_id = (await session.execute(select(Location.id))).scalar_one()
        session.add(StopListEntry(location_id=location_id, **target))


def invalid(response: Any, reason: str) -> None:
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_selection"
    assert response.json()["error"]["details"] == {"reason": reason}


async def test_dish_card(api: Api, seeded: async_sessionmaker[AsyncSession]) -> None:
    cappuccino = await ids(seeded, "Капучино")
    body = api.dish(cappuccino["dish"]).json()
    assert [(s["name"], s["price"], s["available"]) for s in body["sizes"]] == [
        ("250 мл", 20000, True),
        ("400 мл", 25000, True),
    ]
    [addons] = body["groups"]
    assert (addons["name"], addons["min_choice"], addons["max_choice"]) == ("Добавки", 0, 2)
    assert [(m["name"], m["price_delta"]) for m in addons["modifiers"]] == [
        ("Сироп", 3000),
        ("Альтернативное молоко", 10000),
    ]


async def test_dish_card_shows_stopped_options(
    api: Api, seeded: async_sessionmaker[AsyncSession]
) -> None:
    cappuccino = await ids(seeded, "Капучино")
    await stop(seeded, dish_size_id=cappuccino["sizes"]["250 мл"])
    await stop(seeded, modifier_id=await modifier(seeded, "Сироп"))
    body = api.dish(cappuccino["dish"]).json()
    assert [s["available"] for s in body["sizes"]] == [False, True]
    assert [m["available"] for m in body["groups"][0]["modifiers"]] == [False, True]


async def test_hidden_or_missing_dish_is_404(
    api: Api, seeded: async_sessionmaker[AsyncSession]
) -> None:
    cola = await ids(seeded, "Кола")
    async with seeded() as session, session.begin():
        await session.execute(update(Dish).where(Dish.id == cola["dish"]).values(is_hidden=True))
    for dish_id in (cola["dish"], uuid.uuid4()):
        response = api.dish(dish_id)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "dish_not_found"


async def test_simple_dish(api: Api, seeded: async_sessionmaker[AsyncSession]) -> None:
    philadelphia = await ids(seeded, "Филадельфия")
    body = api.price(
        dish_id=philadelphia["dish"], size_id=philadelphia["sizes"][""], quantity=1
    ).json()
    assert body == {
        "unit_price": 69900,
        "total_price": 69900,
        "complete": True,
        "missing_groups": [],
    }


async def test_size_addons_and_quantity(api: Api, seeded: async_sessionmaker[AsyncSession]) -> None:
    cappuccino = await ids(seeded, "Капучино")
    body = api.price(
        dish_id=cappuccino["dish"],
        size_id=cappuccino["sizes"]["400 мл"],
        modifier_ids=[
            await modifier(seeded, "Сироп"),
            await modifier(seeded, "Альтернативное молоко"),
        ],
        quantity=2,
    ).json()
    assert (body["unit_price"], body["total_price"], body["complete"]) == (38000, 76000, True)


async def test_required_group_missing_then_chosen(
    api: Api, seeded: async_sessionmaker[AsyncSession]
) -> None:
    wings = await ids(seeded, "Куриные крылышки в соусе")
    size = wings["sizes"][""]
    incomplete = api.price(dish_id=wings["dish"], size_id=size, quantity=1).json()
    assert incomplete["complete"] is False
    assert [g["name"] for g in incomplete["missing_groups"]] == ["Соус"]
    complete = api.price(
        dish_id=wings["dish"],
        size_id=size,
        modifier_ids=[await modifier(seeded, "Терияки")],
        quantity=1,
    ).json()
    assert (complete["complete"], complete["total_price"]) == (True, 49900)


async def test_too_many_in_a_group(api: Api, seeded: async_sessionmaker[AsyncSession]) -> None:
    wings = await ids(seeded, "Куриные крылышки в соусе")
    invalid(
        api.price(
            dish_id=wings["dish"],
            size_id=wings["sizes"][""],
            modifier_ids=[await modifier(seeded, "BBQ"), await modifier(seeded, "Терияки")],
            quantity=1,
        ),
        "too_many",
    )


async def test_foreign_modifier(api: Api, seeded: async_sessionmaker[AsyncSession]) -> None:
    cappuccino = await ids(seeded, "Капучино")
    invalid(
        api.price(
            dish_id=cappuccino["dish"],
            size_id=cappuccino["sizes"]["250 мл"],
            modifier_ids=[await modifier(seeded, "BBQ")],
            quantity=1,
        ),
        "foreign_modifier",
    )


async def test_foreign_size(api: Api, seeded: async_sessionmaker[AsyncSession]) -> None:
    cappuccino = await ids(seeded, "Капучино")
    fries = await ids(seeded, "Картофель фри")
    invalid(
        api.price(dish_id=cappuccino["dish"], size_id=fries["sizes"]["М"], quantity=1),
        "foreign_size",
    )


async def test_stopped_size_or_modifier(api: Api, seeded: async_sessionmaker[AsyncSession]) -> None:
    cappuccino = await ids(seeded, "Капучино")
    syrup = await modifier(seeded, "Сироп")
    await stop(seeded, dish_size_id=cappuccino["sizes"]["250 мл"])
    await stop(seeded, modifier_id=syrup)
    invalid(
        api.price(dish_id=cappuccino["dish"], size_id=cappuccino["sizes"]["250 мл"], quantity=1),
        "unavailable",
    )
    invalid(
        api.price(
            dish_id=cappuccino["dish"],
            size_id=cappuccino["sizes"]["400 мл"],
            modifier_ids=[syrup],
            quantity=1,
        ),
        "unavailable",
    )


async def test_duplicate_modifier(api: Api, seeded: async_sessionmaker[AsyncSession]) -> None:
    cappuccino = await ids(seeded, "Капучино")
    syrup = await modifier(seeded, "Сироп")
    invalid(
        api.price(
            dish_id=cappuccino["dish"],
            size_id=cappuccino["sizes"]["250 мл"],
            modifier_ids=[syrup, syrup],
            quantity=1,
        ),
        "duplicate_modifier",
    )


async def test_hidden_dish_cannot_be_priced(
    api: Api, seeded: async_sessionmaker[AsyncSession]
) -> None:
    cola = await ids(seeded, "Кола")
    async with seeded() as session, session.begin():
        await session.execute(update(Dish).where(Dish.id == cola["dish"]).values(is_hidden=True))
    invalid(
        api.price(dish_id=cola["dish"], size_id=cola["sizes"][""], quantity=1), "dish_unavailable"
    )


@pytest.mark.parametrize("quantity", [0, 100])
async def test_quantity_bounds(
    api: Api, seeded: async_sessionmaker[AsyncSession], quantity: int
) -> None:
    philadelphia = await ids(seeded, "Филадельфия")
    response = api.price(
        dish_id=philadelphia["dish"], size_id=philadelphia["sizes"][""], quantity=quantity
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_category_group_applies_to_every_dish_of_it(
    api: Api, seeded: async_sessionmaker[AsyncSession]
) -> None:
    espresso = await ids(seeded, "Эспрессо")
    body = api.price(
        dish_id=espresso["dish"],
        size_id=espresso["sizes"][""],
        modifier_ids=[await modifier(seeded, "Альтернативное молоко")],
        quantity=1,
    ).json()
    assert body["total_price"] == 12000 + 10000
