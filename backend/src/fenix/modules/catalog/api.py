"""Public API of `catalog`: functions and DTOs, the only import surface for other modules."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.catalog import menu, seed
from fenix.modules.catalog.menu import MenuCategory, MenuDish

__all__ = ["MenuCategory", "MenuDish", "get_menu", "seed_menu"]


async def get_menu(session: AsyncSession, location_id: uuid.UUID) -> list[MenuCategory]:
    """Visible categories and dishes in menu order, with prices and stop-list state."""
    return await menu.get_menu(session, location_id)


async def seed_menu(session: AsyncSession) -> bool:
    """Idempotent initial menu from the printed PDF; returns True when it was loaded."""
    return await seed.seed_menu(session)
