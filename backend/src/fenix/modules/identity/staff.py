"""Staff memberships and one-time invitations (FR-34, FR-35, AD-7)."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.identity.models import IdentityUser, Invitation, StaffMembership

INVITATION_TTL = timedelta(hours=24)
# Deep-link payload prefix: `/start inv_<token>`.
INVITATION_PREFIX = "inv_"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def is_staff(session: AsyncSession, user_id: uuid.UUID, location_id: uuid.UUID) -> bool:
    statement = select(
        exists().where(
            StaffMembership.user_id == user_id,
            StaffMembership.location_id == location_id,
            StaffMembership.is_active.is_(True),
        )
    )
    return bool((await session.execute(statement)).scalar_one())


async def has_any_staff(session: AsyncSession, location_id: uuid.UUID) -> bool:
    """Active or disabled: once a location had staff, bootstrap is closed for good."""
    statement = select(exists().where(StaffMembership.location_id == location_id))
    return bool((await session.execute(statement)).scalar_one())


async def add_member(session: AsyncSession, user_id: uuid.UUID, location_id: uuid.UUID) -> None:
    """Make the user an active member; re-enables a disabled membership."""
    membership = (
        await session.execute(
            select(StaffMembership).where(
                StaffMembership.user_id == user_id, StaffMembership.location_id == location_id
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        session.add(StaffMembership(user_id=user_id, location_id=location_id))
    else:
        membership.is_active = True
        membership.disabled_at = None
    await session.flush()


async def bootstrap_first_staff(
    session: AsyncSession, user_id: uuid.UUID, location_id: uuid.UUID
) -> bool:
    # Serialise concurrent bootstraps of the same location.
    await session.execute(select(func.pg_advisory_xact_lock(_lock_key(location_id))))
    if await has_any_staff(session, location_id):
        return False
    await add_member(session, user_id, location_id)
    return True


def _lock_key(location_id: uuid.UUID) -> int:
    # pg_advisory_xact_lock takes a signed 64-bit key.
    return int.from_bytes(location_id.bytes[:8], "big", signed=True)


async def create_invitation(
    session: AsyncSession, created_by: uuid.UUID, location_id: uuid.UUID, now: datetime
) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(18)
    expires_at = now + INVITATION_TTL
    session.add(
        Invitation(
            token_hash=hash_token(token),
            location_id=location_id,
            created_by=created_by,
            expires_at=expires_at,
        )
    )
    await session.flush()
    return token, expires_at


async def accept_invitation(
    session: AsyncSession, token: str, user_id: uuid.UUID, now: datetime | None = None
) -> bool:
    """Redeem the token for the user. False for an unknown, used or expired one.

    A user who is already an active member keeps the link unused for a colleague.
    """
    now = now or datetime.now(UTC)
    invitation = (
        await session.execute(select(Invitation).where(Invitation.token_hash == hash_token(token)))
    ).scalar_one_or_none()
    if invitation is None or invitation.used_at is not None or invitation.expires_at <= now:
        return False
    if await is_staff(session, user_id, invitation.location_id):
        return True
    # Conditional update: of two simultaneous redemptions exactly one wins.
    redeemed = await session.execute(
        update(Invitation)
        .where(Invitation.id == invitation.id, Invitation.used_at.is_(None))
        .values(used_at=now, used_by=user_id)
        .returning(Invitation.id)
    )
    if redeemed.first() is None:
        return False
    await add_member(session, user_id, invitation.location_id)
    return True


async def find_user_by_username(session: AsyncSession, username: str) -> IdentityUser | None:
    statement = select(IdentityUser).where(
        func.lower(IdentityUser.username) == username.lstrip("@").lower()
    )
    return (await session.execute(statement)).scalars().first()
