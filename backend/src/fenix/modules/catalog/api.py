"""Public API of `catalog`: functions and DTOs, the only import surface for other modules."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.catalog import dish, menu, pricing, seed
from fenix.modules.catalog.dish import DishDetail, GroupOption, ModifierOption, SizeOption
from fenix.modules.catalog.menu import MenuCategory, MenuDish
from fenix.modules.catalog.pricing import InvalidSelectionError, MissingGroup, Price

__all__ = [
    "DishDetail",
    "GroupOption",
    "InvalidSelectionError",
    "MenuCategory",
    "MenuDish",
    "MissingGroup",
    "ModifierOption",
    "Price",
    "SizeOption",
    "get_dish",
    "get_menu",
    "price",
    "seed_menu",
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
