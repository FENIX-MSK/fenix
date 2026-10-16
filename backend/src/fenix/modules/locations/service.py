from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.locations.models import Location


async def get_default_location(session: AsyncSession) -> Location | None:
    """The only location for now; the first one created once there are several."""
    statement = select(Location).order_by(Location.created_at, Location.id).limit(1)
    return (await session.execute(statement)).scalar_one_or_none()
