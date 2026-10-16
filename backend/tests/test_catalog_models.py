import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.modules.catalog import api as catalog
from fenix.modules.catalog.models import DishSize, Modifier, ModifierGroup, StopListEntry
from fenix.modules.locations import api as locations
from fenix.modules.locations.models import Location


@pytest.fixture
async def ids(session_factory: async_sessionmaker[AsyncSession]) -> dict[str, object]:
    async with session_factory() as session, session.begin():
        await locations.seed_defaults(session)
        await catalog.seed_menu(session)
    async with session_factory() as session:
        return {
            "location": (await session.execute(select(Location.id))).scalar_one(),
            "size": (await session.execute(select(DishSize.id).limit(1))).scalar_one(),
            "modifier": (await session.execute(select(Modifier.id).limit(1))).scalar_one(),
        }


async def add(factory: async_sessionmaker[AsyncSession], **fields: object) -> None:
    async with factory() as session, session.begin():
        session.add(StopListEntry(**fields))


async def test_stop_list_by_size_or_modifier(
    session_factory: async_sessionmaker[AsyncSession], ids: dict[str, object]
) -> None:
    await add(session_factory, location_id=ids["location"], dish_size_id=ids["size"])
    await add(session_factory, location_id=ids["location"], modifier_id=ids["modifier"])


@pytest.mark.parametrize("fields", [{}, {"dish_size_id": "size", "modifier_id": "modifier"}])
async def test_stop_list_needs_exactly_one_target(
    session_factory: async_sessionmaker[AsyncSession],
    ids: dict[str, object],
    fields: dict[str, str],
) -> None:
    with pytest.raises(IntegrityError):
        await add(
            session_factory,
            location_id=ids["location"],
            **{column: ids[key] for column, key in fields.items()},
        )


async def test_stop_list_entry_is_unique_per_location(
    session_factory: async_sessionmaker[AsyncSession], ids: dict[str, object]
) -> None:
    await add(session_factory, location_id=ids["location"], dish_size_id=ids["size"])
    with pytest.raises(IntegrityError):
        await add(session_factory, location_id=ids["location"], dish_size_id=ids["size"])


async def test_group_bounds_are_checked(session_factory: async_sessionmaker[AsyncSession]) -> None:
    with pytest.raises(IntegrityError):
        async with session_factory() as session, session.begin():
            session.add(ModifierGroup(name="Bad", min_choice=2, max_choice=1))
