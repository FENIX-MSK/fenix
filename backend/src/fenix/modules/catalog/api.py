"""Public API of `catalog`: functions and DTOs, the only import surface for other modules."""

from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.catalog import seed


async def seed_menu(session: AsyncSession) -> bool:
    """Idempotent initial menu from the printed PDF; returns True when it was loaded."""
    return await seed.seed_menu(session)
