"""Public API of `catalog`: functions and DTOs, the only import surface for other modules."""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.catalog import dish, editor, menu, pricing, seed
from fenix.modules.catalog.dish import DishDetail, GroupOption, ModifierOption, SizeOption
from fenix.modules.catalog.editor import CatalogEditError, DishInput, SizeInput
from fenix.modules.catalog.menu import MenuCategory, MenuDish
from fenix.modules.catalog.models import Category, Dish
from fenix.modules.catalog.pricing import InvalidSelectionError, MissingGroup, Price

__all__ = [
    "CatalogEditError",
    "DishDetail",
    "DishInput",
    "GroupOption",
    "InvalidSelectionError",
    "MenuCategory",
    "MenuDish",
    "MissingGroup",
    "ModifierOption",
    "Price",
    "SizeInput",
    "SizeOption",
    "StaffCategory",
    "StaffDish",
    "StaffSize",
    "create_category",
    "create_dish",
    "delete_category",
    "delete_dish",
    "get_dish",
    "get_menu",
    "price",
    "reorder_categories",
    "reorder_dishes",
    "seed_menu",
    "staff_catalog",
    "update_category",
    "update_dish",
]


async def get_menu(session: AsyncSession, location_id: uuid.UUID) -> list[MenuCategory]:
    """Visible categories and dishes in menu order, with prices and stop-list state."""
    return await menu.get_menu(session, location_id)


async def get_dish(
    session: AsyncSession, location_id: uuid.UUID, dish_id: uuid.UUID
) -> DishDetail | None:
    """A visible dish with its sizes and modifier groups (dish's first, then category's)."""
    return await dish.get_dish(session, location_id, dish_id)


async def price(
    session: AsyncSession,
    *,
    location_id: uuid.UUID,
    dish_id: uuid.UUID,
    size_id: uuid.UUID,
    modifier_ids: list[uuid.UUID],
    quantity: int,
) -> Price:
    """The single price function (AD-6). Raises InvalidSelectionError for what cannot be
    ordered; an unmet minimum is not an error but `complete=False`."""
    return await pricing.price(
        session,
        location_id=location_id,
        dish_id=dish_id,
        size_id=size_id,
        modifier_ids=modifier_ids,
        quantity=quantity,
    )


async def seed_menu(session: AsyncSession) -> bool:
    """Idempotent initial menu from the printed PDF; returns True when it was loaded."""
    return await seed.seed_menu(session)


@dataclass(frozen=True, slots=True)
class StaffSize:
    id: uuid.UUID
    name: str
    price: int
    portion: str | None


@dataclass(frozen=True, slots=True)
class StaffDish:
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    description: str
    portion: str | None
    is_hidden: bool
    photo_key: str | None
    sizes: list[StaffSize]
    group_ids: list[uuid.UUID]


@dataclass(frozen=True, slots=True)
class StaffCategory:
    id: uuid.UUID
    name: str
    description: str
    is_hidden: bool
    dishes: list[StaffDish]
    group_ids: list[uuid.UUID]


def _staff_dish(row: Dish) -> StaffDish:
    return StaffDish(
        id=row.id,
        category_id=row.category_id,
        name=row.name,
        description=row.description,
        portion=row.portion,
        is_hidden=row.is_hidden,
        photo_key=row.photo_key,
        sizes=[StaffSize(s.id, s.name, s.price, s.portion) for s in row.sizes],
        group_ids=[link.group_id for link in row.modifier_groups],
    )


def _staff_category(row: Category, dishes: list[StaffDish]) -> StaffCategory:
    return StaffCategory(
        id=row.id,
        name=row.name,
        description=row.description,
        is_hidden=row.is_hidden,
        dishes=dishes,
        group_ids=[link.group_id for link in row.modifier_groups],
    )


async def staff_catalog(session: AsyncSession) -> list[StaffCategory]:
    """The whole catalog for the editor, hidden items included, in menu order."""
    return [
        _staff_category(c, [_staff_dish(d) for d in c.dishes])
        for c in await editor.staff_catalog(session)
    ]


async def create_category(
    session: AsyncSession, *, name: str, description: str = "", is_hidden: bool = False
) -> uuid.UUID:
    return (await editor.create_category(session, name, description, is_hidden)).id


async def update_category(
    session: AsyncSession, category_id: uuid.UUID, *, name: str, description: str, is_hidden: bool
) -> None:
    await editor.update_category(session, category_id, name, description, is_hidden)


async def delete_category(session: AsyncSession, category_id: uuid.UUID) -> None:
    """Only an empty category; raises CatalogEditError("category_not_empty")."""
    await editor.delete_category(session, category_id)


async def create_dish(session: AsyncSession, data: DishInput) -> uuid.UUID:
    return (await editor.create_dish(session, data)).id


async def update_dish(session: AsyncSession, dish_id: uuid.UUID, data: DishInput) -> None:
    """Sizes are matched by id: kept, created (no id) or deleted (left out)."""
    await editor.update_dish(session, dish_id, data)


async def delete_dish(session: AsyncSession, dish_id: uuid.UUID) -> None:
    await editor.delete_dish(session, dish_id)


async def reorder_categories(session: AsyncSession, ids: list[uuid.UUID]) -> None:
    await editor.reorder_categories(session, ids)


async def reorder_dishes(
    session: AsyncSession, category_id: uuid.UUID, ids: list[uuid.UUID]
) -> None:
    await editor.reorder_dishes(session, category_id, ids)
