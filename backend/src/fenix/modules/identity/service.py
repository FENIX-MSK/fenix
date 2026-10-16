import re

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.identity.models import IdentityUser

DIRECT_SOURCE = "direct"
# The alphabet and length Telegram allows in a deep-link payload.
_SOURCE_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")


def normalize_source(raw: str | None) -> str:
    if raw and _SOURCE_RE.fullmatch(raw):
        return raw
    return DIRECT_SOURCE


async def ensure_user(
    session: AsyncSession,
    *,
    platform: str,
    external_id: str,
    first_name: str,
    last_name: str | None,
    username: str | None,
    source: str | None,
) -> IdentityUser:
    """Create the user on first contact, refresh the profile when it changed.

    Runs on every authenticated request, so the common path is a single SELECT.
    The source is written only on insert: the first launch's label sticks.
    """
    key = (IdentityUser.platform == platform) & (IdentityUser.external_id == external_id)
    user = (await session.execute(select(IdentityUser).where(key))).scalar_one_or_none()
    if user is None:
        inserted = await session.execute(
            insert(IdentityUser)
            .values(
                platform=platform,
                external_id=external_id,
                first_name=first_name,
                last_name=last_name,
                username=username,
                source=normalize_source(source),
            )
            # A concurrent first request may have created the row in the meantime.
            .on_conflict_do_nothing(
                index_elements=[IdentityUser.platform, IdentityUser.external_id]
            )
            .returning(IdentityUser)
        )
        user = inserted.scalar_one_or_none()
        if user is not None:
            return user
        user = (await session.execute(select(IdentityUser).where(key))).scalar_one()

    if (user.first_name, user.last_name, user.username) != (first_name, last_name, username):
        user.first_name, user.last_name, user.username = first_name, last_name, username
        user.updated_at = func.now()
        await session.flush()
        await session.refresh(user, ["updated_at"])
    return user
