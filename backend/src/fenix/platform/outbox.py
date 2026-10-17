"""Transactional outbox (AD-4): side effects leave the system only through here.

A module records an event in the same transaction as the change that caused it; the
worker delivers it to every subscribed handler with retries. Each handler is recorded as
done per event, so a retry after a partial failure never repeats a handler that succeeded.
"""

import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from fenix.platform.db import Base

log = structlog.get_logger()

EVENT_NAME = re.compile(r"^[a-z_]+\.[a-z_]+\.[a-z_]+$")
MAX_BACKOFF = timedelta(minutes=5)


class OutboxEvent(Base):
    __tablename__ = "platform_outbox_events"
    __table_args__ = (
        Index(
            "ix_platform_outbox_events_pending",
            "available_at",
            postgresql_where=text("processed_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    # `<module>.<entity>.<past_tense>`, e.g. `ordering.order.accepted`.
    name: Mapped[str] = mapped_column(String(128))
    # Self-contained: subscribers never call back the emitting module (AD-4).
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutboxDelivery(Base):
    """A handler that has already processed an event (idempotency by event id)."""

    __tablename__ = "platform_outbox_deliveries"

    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform_outbox_events.id", ondelete="CASCADE"), primary_key=True
    )
    handler: Mapped[str] = mapped_column(String(128), primary_key=True)
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


def emit(session: AsyncSession, name: str, payload: dict[str, Any]) -> None:
    """Record an event; it is delivered only if the surrounding transaction commits."""
    if not EVENT_NAME.match(name):
        raise ValueError(f"bad event name: {name}")
    session.add(OutboxEvent(name=name, payload=payload))


@dataclass(frozen=True, slots=True)
class Event:
    id: uuid.UUID
    name: str
    payload: dict[str, Any]
    created_at: datetime


Handler = Callable[[AsyncSession, Event], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class Subscription:
    """`pattern` is an exact name or a prefix ending in `*` (`ordering.order.*`)."""

    pattern: str
    name: str
    handler: Handler

    def matches(self, event_name: str) -> bool:
        if self.pattern.endswith("*"):
            return event_name.startswith(self.pattern[:-1])
        return event_name == self.pattern


def backoff(attempts: int) -> timedelta:
    return min(timedelta(seconds=2**attempts), MAX_BACKOFF)


@dataclass
class Dispatcher:
    subscriptions: list[Subscription] = field(default_factory=list)

    def subscribe(self, pattern: str, name: str, handler: Handler) -> None:
        if any(s.name == name and s.pattern == pattern for s in self.subscriptions):
            raise ValueError(f"duplicate subscription {name} on {pattern}")
        self.subscriptions.append(Subscription(pattern, name, handler))

    async def deliver_next(self, factory: async_sessionmaker[AsyncSession], now: datetime) -> bool:
        """Process one due event in its own transaction; False when nothing is due."""
        async with factory() as session, session.begin():
            event = (
                await session.execute(
                    select(OutboxEvent)
                    .where(OutboxEvent.processed_at.is_(None), OutboxEvent.available_at <= now)
                    .order_by(OutboxEvent.available_at, OutboxEvent.id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
            ).scalar_one_or_none()
            if event is None:
                return False
            done = set(
                (
                    await session.execute(
                        select(OutboxDelivery.handler).where(OutboxDelivery.event_id == event.id)
                    )
                ).scalars()
            )
            snapshot = Event(event.id, event.name, event.payload, event.created_at)
            failed: list[str] = []
            for subscription in self.subscriptions:
                if subscription.name in done or not subscription.matches(event.name):
                    continue
                try:
                    async with session.begin_nested():
                        await subscription.handler(session, snapshot)
                        session.add(OutboxDelivery(event_id=event.id, handler=subscription.name))
                        await session.flush()
                except Exception as exc:
                    log.warning(
                        "outbox.handler_failed",
                        event_name=event.name,
                        event_id=str(event.id),
                        handler=subscription.name,
                        attempt=event.attempts + 1,
                        error=repr(exc),
                    )
                    failed.append(f"{subscription.name}: {exc!r}")
            if failed:
                # Retried until it succeeds; the order itself is never blocked (NFR-3).
                event.attempts += 1
                event.last_error = "\n".join(failed)[:4000]
                event.available_at = now + backoff(event.attempts)
            else:
                event.processed_at = now
            return True

    async def deliver_due(
        self, factory: async_sessionmaker[AsyncSession], now: datetime, limit: int = 100
    ) -> int:
        delivered = 0
        while delivered < limit and await self.deliver_next(factory, now):
            delivered += 1
        return delivered
