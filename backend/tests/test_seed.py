from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.modules.locations import api as locations
from fenix.modules.locations.models import Location, OpeningHours


async def counts(factory: async_sessionmaker[AsyncSession]) -> tuple[int, int]:
    async with factory() as session:
        return (
            (await session.execute(select(func.count()).select_from(Location))).scalar_one(),
            (await session.execute(select(func.count()).select_from(OpeningHours))).scalar_one(),
        )


async def test_seed_creates_location_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session, session.begin():
        assert await locations.seed_defaults(session) is True
    async with session_factory() as session, session.begin():
        assert await locations.seed_defaults(session) is False
    assert await counts(session_factory) == (1, 7)


async def test_seed_keeps_staff_edits(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session, session.begin():
        await locations.seed_defaults(session)
    async with session_factory() as session, session.begin():
        location = (await session.execute(select(Location))).scalar_one()
        location.phone = "+7 (999) 123-45-67"
    async with session_factory() as session, session.begin():
        await locations.seed_defaults(session)
    async with session_factory() as session:
        assert (await session.execute(select(Location.phone))).scalar_one() == "+7 (999) 123-45-67"
