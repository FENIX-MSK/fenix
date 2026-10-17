"""Public API of `notifications`: functions and DTOs, the only import surface for other modules."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.notifications import alerts, handlers, staff_chat
from fenix.modules.notifications.gateway import Button, MessengerGateway, Undeliverable
from fenix.modules.notifications.handlers import Links
from fenix.modules.notifications.staff_chat import StaffChatInfo
from fenix.platform.outbox import Subscription

__all__ = [
    "Button",
    "Links",
    "MessengerGateway",
    "StaffChatInfo",
    "Undeliverable",
    "bind_alert_chat",
    "bind_staff_chat",
    "get_staff_chat",
    "queue_alerts",
    "subscriptions",
]


def subscriptions(gateway: MessengerGateway, links: Links) -> list[Subscription]:
    """Outbox handlers that message guests, the staff chat and the alert chat."""
    return [*handlers.subscriptions(gateway, links), *alerts.subscriptions(gateway)]


async def bind_alert_chat(
    session: AsyncSession, *, platform: str, chat_id: str, title: str
) -> None:
    """`/alerts` in a group: monitoring alerts go there from now on."""
    await alerts.bind(session, platform=platform, chat_id=chat_id, title=title)


def queue_alerts(session: AsyncSession, items: list[dict[str, str]]) -> None:
    """Grafana's alerts, delivered to the alert chat with retries (outbox)."""
    alerts.queue(session, items)


async def get_staff_chat(session: AsyncSession, location_id: uuid.UUID) -> StaffChatInfo | None:
    return await staff_chat.get(session, location_id)


async def bind_staff_chat(
    session: AsyncSession,
    location_id: uuid.UUID,
    *,
    platform: str,
    chat_id: str,
    title: str,
    user_id: uuid.UUID | None,
) -> bool:
    """One chat per location; binding another one replaces it (returns True then)."""
    return await staff_chat.bind(
        session, location_id, platform=platform, chat_id=chat_id, title=title, user_id=user_id
    )
