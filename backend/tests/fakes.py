"""Stand-ins for the messenger and Redis, recording what would have been sent."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.modules.notifications import api as notifications
from fenix.platform.outbox import Dispatcher
from fenix.worker import build_dispatcher


@dataclass
class Sent:
    platform: str
    chat_id: str
    text: str
    buttons: list[notifications.Button] | None


@dataclass
class FakeGateway:
    sent: list[Sent] = field(default_factory=list)
    # Raised on the next sends, then cleared one by one.
    failures: list[Exception] = field(default_factory=list)

    async def send(
        self,
        platform: str,
        chat_id: str,
        text: str,
        buttons: list[notifications.Button] | None = None,
    ) -> None:
        if self.failures:
            raise self.failures.pop(0)
        self.sent.append(Sent(platform, chat_id, text, buttons))


@dataclass
class FakeRedis:
    published: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    async def publish(self, channel: str, message: str) -> None:
        self.published.append((channel, json.loads(message)))


@dataclass
class Worker:
    gateway: FakeGateway
    redis: FakeRedis
    dispatcher: Dispatcher
    factory: async_sessionmaker[AsyncSession]

    async def run(self, now: datetime | None = None) -> int:
        return await self.dispatcher.deliver_due(self.factory, now or datetime.now(UTC))


def make_worker(factory: async_sessionmaker[AsyncSession]) -> Worker:
    gateway, redis = FakeGateway(), FakeRedis()
    links = notifications.Links("https://app.test", "fenix_test_bot")
    dispatcher = build_dispatcher(gateway, links, redis)  # type: ignore[arg-type]
    return Worker(gateway, redis, dispatcher, factory)
