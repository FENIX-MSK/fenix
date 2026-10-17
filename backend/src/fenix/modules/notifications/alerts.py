"""Monitoring alerts to a Telegram chat (NFR-6), through the same outbox and gateway."""

from html import escape

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.notifications.gateway import MessengerGateway, Undeliverable
from fenix.modules.notifications.models import AlertChat
from fenix.platform import outbox
from fenix.platform.outbox import Event, Handler, Subscription

log = structlog.get_logger()

EVENT = "notifications.alert.received"


async def bind(session: AsyncSession, *, platform: str, chat_id: str, title: str) -> None:
    row = await session.get(AlertChat, 1)
    if row is None:
        session.add(AlertChat(id=1, platform=platform, chat_id=chat_id, title=title[:256]))
    else:
        row.platform, row.chat_id, row.title = platform, chat_id, title[:256]
    await session.flush()


def queue(session: AsyncSession, alerts: list[dict[str, str]]) -> None:
    """[{"status": "firing" | "resolved", "name": ..., "summary": ...}]"""
    if alerts:
        outbox.emit(session, EVENT, {"alerts": alerts})


def render(alerts: list[dict[str, str]]) -> str:
    lines = []
    for alert in alerts:
        mark = "🔴" if alert.get("status") == "firing" else "✅"
        summary = f" — {escape(alert['summary'])}" if alert.get("summary") else ""
        lines.append(f"{mark} <b>{escape(alert.get('name', 'alert'))}</b>{summary}")
    return "\n".join(lines)


def handler(gateway: MessengerGateway) -> Handler:
    async def handle(session: AsyncSession, event: Event) -> None:
        chat = await session.get(AlertChat, 1)
        if chat is None:
            log.warning("notifications.no_alert_chat", alerts=event.payload["alerts"])
            return
        try:
            await gateway.send(chat.platform, chat.chat_id, render(event.payload["alerts"]))
        except Undeliverable as exc:
            log.warning("notifications.alert_chat_undeliverable", error=str(exc))

    return handle


def subscriptions(gateway: MessengerGateway) -> list[Subscription]:
    return [Subscription(EVENT, "notifications.alerts", handler(gateway))]
