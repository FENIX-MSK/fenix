from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.modules.identity import api as identity
from fenix.modules.identity.models import IdentityUser


async def ensure(
    factory: async_sessionmaker[AsyncSession], source: str | None, **profile: str
) -> identity.User:
    async with factory() as session, session.begin():
        return await identity.ensure_user(
            session,
            platform=identity.Platform.TELEGRAM,
            external_id="42",
            first_name=profile.get("first_name", "Аня"),
            username=profile.get("username"),
            source=source,
        )


async def count(factory: async_sessionmaker[AsyncSession]) -> int:
    async with factory() as session:
        return (await session.execute(select(func.count()).select_from(IdentityUser))).scalar_one()


async def test_new_user_without_label_is_direct(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = await ensure(session_factory, None)
    assert user.source == "direct"
    assert user.platform is identity.Platform.TELEGRAM
    assert user.id.version == 7


async def test_first_label_sticks(session_factory: async_sessionmaker[AsyncSession]) -> None:
    first = await ensure(session_factory, "qr_table")
    again = await ensure(session_factory, "promo", first_name="Анна", username="anna")
    assert again.id == first.id
    assert again.source == "qr_table"
    assert (again.first_name, again.username) == ("Анна", "anna")
    assert await count(session_factory) == 1


async def test_malformed_label_becomes_direct(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    assert (await ensure(session_factory, "qr table!")).source == "direct"


async def test_overlong_label_becomes_direct(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    assert (await ensure(session_factory, "a" * 65)).source == "direct"


async def test_same_id_on_another_platform_is_another_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    telegram = await ensure(session_factory, None)
    async with session_factory() as session, session.begin():
        other = await identity.ensure_user(
            session, platform=identity.Platform.MAX, external_id="42", first_name="Аня"
        )
    assert other.id != telegram.id


async def updated_at(factory: async_sessionmaker[AsyncSession]) -> object:
    async with factory() as session:
        return (await session.execute(select(IdentityUser.updated_at))).scalar_one()


async def test_unchanged_profile_is_not_rewritten(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await ensure(session_factory, None)
    before = await updated_at(session_factory)
    await ensure(session_factory, None)
    assert await updated_at(session_factory) == before
    await ensure(session_factory, None, first_name="Анна")
    assert await updated_at(session_factory) != before
