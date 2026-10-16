"""Public API of `identity`: functions and DTOs, the only import surface for other modules."""

import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.identity import service


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
    return User(
        id=row.id,
        platform=Platform(row.platform),
        external_id=row.external_id,
        first_name=row.first_name,
        last_name=row.last_name,
        username=row.username,
        source=row.source,
    )
