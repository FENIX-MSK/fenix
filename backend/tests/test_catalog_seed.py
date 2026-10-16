import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from fenix.modules.catalog import api as catalog
from fenix.modules.catalog.models import (
    Category,
    CategoryModifierGroup,
    Dish,
    DishModifierGroup,
    DishSize,
    Modifier,
    ModifierGroup,
)

DISHES_PER_CATEGORY = {
    "Роллы": 19,
    "Сеты": 5,
    "Пицца": 8,
    "Закуски": 7,
    "Лепёшки": 2,
    "Бургеры": 7,
    "Кофе": 10,
    "Лимонады": 3,
    "Напитки": 5,
    "Десерты": 4,
}


@pytest.fixture
async def seeded(
    session_factory: async_sessionmaker[AsyncSession],
) -> async_sessionmaker[AsyncSession]:
    async with session_factory() as session, session.begin():
        assert await catalog.seed_menu(session) is True
    return session_factory


async def dish(session: AsyncSession, name: str) -> Dish:
    statement = (
        select(Dish)
        .where(Dish.name == name)
        .options(
            selectinload(Dish.sizes),
            selectinload(Dish.modifier_groups)
            .selectinload(DishModifierGroup.group)
            .selectinload(ModifierGroup.modifiers),
        )
    )
    return (await session.execute(statement)).scalar_one()


async def test_categories_in_menu_order(seeded: async_sessionmaker[AsyncSession]) -> None:
    async with seeded() as session:
        rows = await session.execute(
            select(Category.name, func.count(Dish.id))
            .join(Dish)
            .group_by(Category.id)
            .order_by(Category.position)
        )
        assert {name: count for name, count in rows} == DISHES_PER_CATEGORY
        assert list(DISHES_PER_CATEGORY) == [
            name
            for (name,) in await session.execute(select(Category.name).order_by(Category.position))
        ]


async def test_prices_are_kopecks(seeded: async_sessionmaker[AsyncSession]) -> None:
    async with seeded() as session:
        philadelphia = await dish(session, "Филадельфия")
        assert [(s.name, s.price) for s in philadelphia.sizes] == [("", 69900)]
        assert philadelphia.portion == "170 г"
        assert philadelphia.description == "рис, лосось, нори, огурец, творожный сыр"
        total = (await session.execute(select(func.sum(DishSize.price)))).scalar_one()
        # Every price is a whole number of rubles in the PDF.
        assert total % 100 == 0


@pytest.mark.parametrize(
    ("name", "sizes"),
    [
        ("Картофель фри", [("М", 12900, None), ("Б", 19900, None)]),
        ("Капучино", [("250 мл", 20000, "250 мл"), ("400 мл", 25000, "400 мл")]),
        ("Какао с маршмеллоу", [("250 мл", 25000, "250 мл"), ("400 мл", 35000, "400 мл")]),
    ],
)
async def test_sized_dishes(
    seeded: async_sessionmaker[AsyncSession], name: str, sizes: list[tuple[str, int, str | None]]
) -> None:
    async with seeded() as session:
        found = await dish(session, name)
        assert [(s.name, s.price, s.portion) for s in found.sizes] == sizes


async def test_every_dish_has_a_size(seeded: async_sessionmaker[AsyncSession]) -> None:
    async with seeded() as session:
        without = await session.execute(select(Dish.name).where(~Dish.sizes.any()))
        assert without.scalars().all() == []


async def test_wing_sauce_is_a_required_free_choice(
    seeded: async_sessionmaker[AsyncSession],
) -> None:
    async with seeded() as session:
        wings = await dish(session, "Куриные крылышки в соусе")
        [link] = wings.modifier_groups
        group = link.group
        assert (group.name, group.min_choice, group.max_choice) == ("Соус", 1, 1)
        assert [(m.name, m.price_delta) for m in group.modifiers] == [
            ("BBQ", 0),
            ("Кисло-сладкий", 0),
            ("Сладкий чили", 0),
            ("Терияки", 0),
        ]


async def test_burger_patty_is_one_shared_group(seeded: async_sessionmaker[AsyncSession]) -> None:
    async with seeded() as session:
        groups = {
            name: (await dish(session, name)).modifier_groups
            for name in ("Black Angus", "Северный", "Криспи", "Классик")
        }
        assert groups["Классик"] == []
        patty_ids = {links[0].group_id for name, links in groups.items() if name != "Классик"}
        assert len(patty_ids) == 1
        patty = groups["Black Angus"][0].group
        assert (patty.min_choice, patty.max_choice) == (1, 1)
        assert [m.name for m in patty.modifiers] == ["Мраморная котлета", "Рваная говядина"]


async def test_coffee_addons_belong_to_the_category(
    seeded: async_sessionmaker[AsyncSession],
) -> None:
    async with seeded() as session:
        link = (
            await session.execute(
                select(CategoryModifierGroup)
                .join(Category)
                .where(Category.name == "Кофе")
                .options(
                    selectinload(CategoryModifierGroup.group).selectinload(ModifierGroup.modifiers)
                )
            )
        ).scalar_one()
        group = link.group
        assert (group.name, group.min_choice, group.max_choice) == ("Добавки", 0, 2)
        assert [(m.name, m.price_delta) for m in group.modifiers] == [
            ("Сироп", 3000),
            ("Альтернативное молоко", 10000),
        ]
        assert (await dish(session, "Капучино")).modifier_groups == []


async def test_sets_describe_their_rolls(seeded: async_sessionmaker[AsyncSession]) -> None:
    async with seeded() as session:
        unagi = await dish(session, "Сет Унаги")
        assert unagi.description == "ролл Канада, ролл Дракон, ролл с угрём"
        assert unagi.sizes[0].price == 149900


async def test_pizza_category_is_32_cm(seeded: async_sessionmaker[AsyncSession]) -> None:
    async with seeded() as session:
        description = await session.execute(
            select(Category.description).where(Category.name == "Пицца")
        )
        assert description.scalar_one() == "32 см"


async def test_second_run_changes_nothing(seeded: async_sessionmaker[AsyncSession]) -> None:
    async def counts() -> list[int]:
        async with seeded() as session:
            return [
                (await session.execute(select(func.count()).select_from(model))).scalar_one()
                for model in (Category, Dish, DishSize, ModifierGroup, Modifier)
            ]

    before = await counts()
    async with seeded() as session, session.begin():
        assert await catalog.seed_menu(session) is False
    assert await counts() == before
    # 70 dishes, three of them with two sizes; three groups with 4 + 2 + 2 options.
    assert before == [10, 70, 73, 3, 8]


async def test_second_run_does_not_restore_removed_dishes(
    seeded: async_sessionmaker[AsyncSession],
) -> None:
    async with seeded() as session, session.begin():
        await session.delete(await dish(session, "Кола"))
    async with seeded() as session, session.begin():
        await catalog.seed_menu(session)
    async with seeded() as session:
        assert (await session.execute(select(Dish).where(Dish.name == "Кола"))).first() is None
