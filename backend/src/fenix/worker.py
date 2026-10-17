"""Background worker (AD-4, AD-13): delivers the outbox and runs periodic jobs.

A plain asyncio process rather than a task queue: every deferred action is a row in the
database (an outbox event, an order with a deadline), so a restart loses nothing and the
loop simply picks up what is due. Polling twice a second keeps notifications and board
updates well inside the 5 s budget (NFR-4).
"""

import asyncio
import contextlib
import signal
from datetime import UTC, datetime

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.modules.notifications import api as notifications
from fenix.modules.ordering import api as ordering
from fenix.modules.payments import api as payments
from fenix.platform import realtime
from fenix.platform.config import get_settings
from fenix.platform.db import create_engine, create_session_factory
from fenix.platform.logging import configure_logging
from fenix.platform.outbox import Dispatcher, Event, Handler
from fenix.telegram.bot import bot_username, create_bot
from fenix.telegram.gateway import TelegramGateway

log = structlog.get_logger()

POLL_SECONDS = 0.5
SWEEP_SECONDS = 30.0


def realtime_handler(redis: Redis) -> Handler:
    """Signal the staff board and the guest's order screen (AD-5)."""

    async def handle(session: AsyncSession, event: Event) -> None:
        payload = event.payload
        signal = {
            "event": event.name,
            "order_id": payload["order_id"],
            "status": payload.get("status"),
            "version": payload.get("version"),
        }
        await realtime.publish(redis, realtime.staff_channel(payload["location_id"]), signal)
        await realtime.publish(redis, realtime.order_channel(payload["order_id"]), signal)

    return handle


def build_dispatcher(
    gateway: notifications.MessengerGateway, links: notifications.Links, redis: Redis
) -> Dispatcher:
    dispatcher = Dispatcher()
    for subscription in [
        *ordering.subscriptions(),
        *payments.subscriptions(),
        *notifications.subscriptions(gateway, links),
    ]:
        dispatcher.subscribe(subscription.pattern, subscription.name, subscription.handler)
    for pattern in ("ordering.order.*", "payments.payment.*"):
        dispatcher.subscribe(pattern, "realtime.signal", realtime_handler(redis))
    return dispatcher


async def cancel_overdue_unpaid(factory: async_sessionmaker[AsyncSession], now: datetime) -> int:
    """FR-13: unpaid online orders are cancelled after the location's timeout."""
    async with factory() as session:
        overdue = await ordering.overdue_unpaid(session, now)
    cancelled = 0
    for order_id in overdue:
        async with factory() as session, session.begin():
            # The attempt is closed first, so a late "paid" from the provider is refused.
            await payments.cancel_pending(session, order_id)
            if await ordering.cancel_unpaid(session, order_id, now):
                cancelled += 1
    if cancelled:
        log.info("worker.unpaid_cancelled", count=cancelled)
    return cancelled


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json=settings.is_production)
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    redis = Redis.from_url(settings.redis_url)
    bot = create_bot(settings)
    username: str | None = None
    try:
        username = await bot_username(settings)
    except Exception as exc:  # Telegram unreachable at start: links come without the bot
        log.warning("worker.bot_username_unknown", error=repr(exc))
    dispatcher = build_dispatcher(
        TelegramGateway(bot), notifications.Links(settings.webapp_url, username), redis
    )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    log.info("worker.started")
    last_sweep = 0.0
    try:
        while not stop.is_set():
            try:
                delivered = await dispatcher.deliver_due(factory, datetime.now(UTC))
                if loop.time() - last_sweep >= SWEEP_SECONDS:
                    last_sweep = loop.time()
                    await cancel_overdue_unpaid(factory, datetime.now(UTC))
            except Exception:
                # The database or Redis blinked: keep the process, try again shortly.
                log.exception("worker.iteration_failed")
                delivered = 0
            if not delivered:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), POLL_SECONDS)
    finally:
        log.info("worker.stopping")
        await bot.session.close()
        await redis.aclose()
        await engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
