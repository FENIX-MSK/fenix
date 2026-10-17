import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.notifications.models import StaffChat


@dataclass(frozen=True, slots=True)
class StaffChatInfo:
    location_id: uuid.UUID
    platform: str
    chat_id: str
    title: str


async def get(session: AsyncSession, location_id: uuid.UUID) -> StaffChatInfo | None:
    row = await session.get(StaffChat, location_id)
    if row is None:
        return None
    return StaffChatInfo(row.location_id, row.platform, row.chat_id, row.title)


async def bind(
    session: AsyncSession,
    location_id: uuid.UUID,
    *,
    platform: str,
    chat_id: str,
    title: str,
    user_id: uuid.UUID | None,
) -> bool:
    """Make the chat the location's staff chat; True when it replaced another chat."""
    row = await session.get(StaffChat, location_id)
    if row is None:
        session.add(
            StaffChat(
                location_id=location_id,
                platform=platform,
                chat_id=chat_id,
                title=title[:256],
                bound_by=user_id,
            )
        )
        await session.flush()
        return False
    replaced = (row.platform, row.chat_id) != (platform, chat_id)
    row.platform, row.chat_id, row.title, row.bound_by = platform, chat_id, title[:256], user_id
    await session.flush()
    return replaced
