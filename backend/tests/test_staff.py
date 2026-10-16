from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.modules.identity import api as identity
from fenix.modules.identity import staff
from fenix.modules.identity.models import Invitation, StaffMembership
from fenix.modules.locations import api as locations


async def user(
    factory: async_sessionmaker[AsyncSession], telegram_id: int, username: str | None = None
) -> identity.User:
    async with factory() as session, session.begin():
        return await identity.ensure_user(
            session,
            platform=identity.Platform.TELEGRAM,
            external_id=str(telegram_id),
            first_name=f"User {telegram_id}",
            username=username,
        )


async def location(factory: async_sessionmaker[AsyncSession]) -> object:
    async with factory() as session:
        return await locations.get_default_location_id(session)


async def test_bootstrap_only_while_location_has_no_staff(
    seeded: async_sessionmaker[AsyncSession],
) -> None:
    first, second = await user(seeded, 1), await user(seeded, 2)
    location_id = await location(seeded)
    async with seeded() as session, session.begin():
        assert await identity.bootstrap_first_staff(session, first.id, location_id) is True
    async with seeded() as session, session.begin():
        assert await identity.bootstrap_first_staff(session, second.id, location_id) is False
        assert await identity.is_staff(session, first.id, location_id)
        assert not await identity.is_staff(session, second.id, location_id)


async def test_bootstrap_closed_after_staff_was_disabled(
    seeded: async_sessionmaker[AsyncSession],
) -> None:
    first, second = await user(seeded, 1), await user(seeded, 2)
    location_id = await location(seeded)
    async with seeded() as session, session.begin():
        await identity.bootstrap_first_staff(session, first.id, location_id)
    async with seeded() as session, session.begin():
        membership = (await session.execute(select(StaffMembership))).scalar_one()
        membership.is_active = False
    async with seeded() as session, session.begin():
        assert await identity.bootstrap_first_staff(session, second.id, location_id) is False


async def invite(factory: async_sessionmaker[AsyncSession], now: datetime) -> str:
    owner = await user(factory, 1)
    location_id = await location(factory)
    async with factory() as session, session.begin():
        await identity.bootstrap_first_staff(session, owner.id, location_id)
        token, expires_at = await identity.create_invitation(session, owner.id, location_id, now)
    assert expires_at == now + timedelta(hours=24)
    return token


async def accept(
    factory: async_sessionmaker[AsyncSession],
    token: str,
    telegram_id: int,
    now: datetime | None = None,
) -> bool:
    guest = await user(factory, telegram_id)
    async with factory() as session, session.begin():
        return await staff.accept_invitation(session, token, guest.id, now)


async def test_invitation_is_one_time(seeded: async_sessionmaker[AsyncSession]) -> None:
    token = await invite(seeded, datetime.now(UTC))
    assert await accept(seeded, token, 2) is True
    assert await accept(seeded, token, 3) is False
    location_id = await location(seeded)
    async with seeded() as session:
        assert await identity.is_staff(session, (await user(seeded, 2)).id, location_id)
        assert not await identity.is_staff(session, (await user(seeded, 3)).id, location_id)


async def test_expired_and_unknown_invitations(seeded: async_sessionmaker[AsyncSession]) -> None:
    created = datetime.now(UTC) - timedelta(hours=24, seconds=1)
    token = await invite(seeded, created)
    assert await accept(seeded, token, 2) is False
    assert await accept(seeded, "made-up", 2) is False


async def test_staff_member_does_not_burn_the_link(
    seeded: async_sessionmaker[AsyncSession],
) -> None:
    token = await invite(seeded, datetime.now(UTC))
    assert await accept(seeded, token, 1) is True
    assert await accept(seeded, token, 2) is True


async def test_only_the_hash_is_stored(seeded: async_sessionmaker[AsyncSession]) -> None:
    token = await invite(seeded, datetime.now(UTC))
    async with seeded() as session:
        stored = (await session.execute(select(Invitation.token_hash))).scalar_one()
    assert token not in stored
    assert stored == staff.hash_token(token)


async def test_disabled_member_comes_back_by_invitation(
    seeded: async_sessionmaker[AsyncSession],
) -> None:
    token = await invite(seeded, datetime.now(UTC))
    await accept(seeded, token, 2)
    async with seeded() as session, session.begin():
        guest = await user(seeded, 2)
        membership = (
            await session.execute(
                select(StaffMembership).where(StaffMembership.user_id == guest.id)
            )
        ).scalar_one()
        membership.is_active = False
    second = await invite(seeded, datetime.now(UTC))
    assert await accept(seeded, second, 2) is True
    async with seeded() as session:
        count = (
            await session.execute(select(func.count()).select_from(StaffMembership))
        ).scalar_one()
    assert count == 2


@pytest.mark.parametrize("username", ["Owner", "@owner", "OWNER"])
async def test_find_user_by_username_ignores_case_and_at(
    seeded: async_sessionmaker[AsyncSession], username: str
) -> None:
    await user(seeded, 5, "owner")
    async with seeded() as session:
        found = await identity.find_user_by_username(session, username)
    assert found is not None and found.external_id == "5"
