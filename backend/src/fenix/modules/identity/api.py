"""Public API of `identity`: functions and DTOs, the only import surface for other modules."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.identity import contact, service, staff
from fenix.modules.identity.contact import Contact, ContactError
from fenix.modules.identity.models import IdentityUser
from fenix.modules.identity.staff import (
    INVITATION_PREFIX,
    INVITATION_TTL,
    LastStaffMemberError,
    StaffMemberNotFoundError,
)

__all__ = [
    "INVITATION_PREFIX",
    "INVITATION_TTL",
    "Contact",
    "ContactError",
    "LastStaffMemberError",
    "Platform",
    "StaffMember",
    "StaffMemberNotFoundError",
    "User",
    "accept_invitation",
    "bootstrap_first_staff",
    "create_invitation",
    "disable_staff",
    "ensure_user",
    "find_user",
    "find_user_by_username",
    "get_contact",
    "get_user",
    "grant_staff",
    "is_staff",
    "list_staff",
    "remove_staff_membership",
    "update_contact",
]


class Platform(StrEnum):
    TELEGRAM = "telegram"
    MAX = "max"


@dataclass(frozen=True, slots=True)
class User:
    id: uuid.UUID
    platform: Platform
    external_id: str
    first_name: str
    last_name: str | None
    username: str | None
    source: str


@dataclass(frozen=True, slots=True)
class StaffMember:
    user_id: uuid.UUID
    first_name: str
    last_name: str | None
    username: str | None
    since: datetime


async def ensure_user(
    session: AsyncSession,
    *,
    platform: Platform,
    external_id: str,
    first_name: str,
    last_name: str | None = None,
    username: str | None = None,
    source: str | None = None,
) -> User:
    """Return the user for (platform, external_id), creating it on first contact.

    `source` is the launch label (e.g. `qr_table`); it is stored only when the user is
    created, and an absent or malformed label becomes `direct`.
    """
    row = await service.ensure_user(
        session,
        platform=platform.value,
        external_id=external_id,
        first_name=first_name,
        last_name=last_name,
        username=username,
        source=source,
    )
    return _user(row)


def _user(row: IdentityUser) -> User:
    return User(
        id=row.id,
        platform=Platform(row.platform),
        external_id=row.external_id,
        first_name=row.first_name,
        last_name=row.last_name,
        username=row.username,
        source=row.source,
    )


async def find_user(session: AsyncSession, platform: Platform, external_id: str) -> User | None:
    row = (
        await session.execute(
            select(IdentityUser).where(
                IdentityUser.platform == platform.value, IdentityUser.external_id == external_id
            )
        )
    ).scalar_one_or_none()
    return _user(row) if row else None


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    row = await session.get(IdentityUser, user_id)
    return _user(row) if row else None


async def find_user_by_username(session: AsyncSession, username: str) -> User | None:
    row = await staff.find_user_by_username(session, username)
    return _user(row) if row else None


async def is_staff(session: AsyncSession, user_id: uuid.UUID, location_id: uuid.UUID) -> bool:
    """An active staff membership at the location (AD-7)."""
    return await staff.is_staff(session, user_id, location_id)


async def bootstrap_first_staff(
    session: AsyncSession, user_id: uuid.UUID, location_id: uuid.UUID
) -> bool:
    """Make the user the first staff member; False once the location has ever had staff."""
    return await staff.bootstrap_first_staff(session, user_id, location_id)


async def create_invitation(
    session: AsyncSession, created_by: uuid.UUID, location_id: uuid.UUID, now: datetime
) -> tuple[str, datetime]:
    """A one-time token valid for INVITATION_TTL; only its hash is stored."""
    return await staff.create_invitation(session, created_by, location_id, now)


async def accept_invitation(session: AsyncSession, token: str, user_id: uuid.UUID) -> bool:
    """Redeem an invitation; False when it is unknown, used or expired."""
    return await staff.accept_invitation(session, token, user_id)


async def list_staff(session: AsyncSession, location_id: uuid.UUID) -> list[StaffMember]:
    """Active staff of the location, oldest first."""
    return [
        StaffMember(
            user_id=m.user_id,
            first_name=m.user.first_name,
            last_name=m.user.last_name,
            username=m.user.username,
            since=m.created_at,
        )
        for m in await staff.list_staff(session, location_id)
    ]


async def disable_staff(
    session: AsyncSession, location_id: uuid.UUID, user_id: uuid.UUID, now: datetime
) -> None:
    """Revoke access at once. Raises StaffMemberNotFoundError, LastStaffMemberError."""
    await staff.disable_staff(session, location_id, user_id, now)


async def grant_staff(session: AsyncSession, user_id: uuid.UUID, location_id: uuid.UUID) -> None:
    """Server-side grant without an invitation (smoke test, operations)."""
    await staff.add_member(session, user_id, location_id)


async def remove_staff_membership(
    session: AsyncSession, user_id: uuid.UUID, location_id: uuid.UUID
) -> None:
    """Delete the membership row entirely, leaving no trace in the staff list."""
    await staff.remove_member(session, user_id, location_id)


async def get_contact(session: AsyncSession, user_id: uuid.UUID) -> Contact:
    return await contact.get(session, user_id)


async def update_contact(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    first_name: str | None = None,
    phone: str | None = None,
    phone_verified: bool = False,
    consent: bool = False,
    now: datetime,
) -> Contact:
    """Raises ContactError: bad_phone, name_required. Consent is recorded once."""
    return await contact.update(
        session,
        user_id,
        first_name=first_name,
        phone=phone,
        phone_verified=phone_verified,
        consent=consent,
        now=now,
    )
