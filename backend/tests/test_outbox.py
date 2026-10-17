from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.platform import outbox
from fenix.platform.outbox import Dispatcher, Event, OutboxEvent

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


async def emit(
    factory: async_sessionmaker[AsyncSession], name: str = "ordering.order.placed"
) -> None:
    async with factory() as session, session.begin():
        outbox.emit(session, name, {"n": 1})


def test_event_names_follow_the_convention() -> None:
    with pytest.raises(ValueError):
        outbox.emit(None, "OrderPlaced", {})  # type: ignore[arg-type]


async def test_rolled_back_change_emits_nothing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session, session.begin():
        outbox.emit(session, "ordering.order.placed", {})
        await session.rollback()
    async with session_factory() as session:
        assert (await session.execute(select(OutboxEvent))).scalars().all() == []


async def test_handlers_run_once_and_failures_are_retried_with_backoff(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    calls: dict[str, int] = {"ok": 0, "flaky": 0}
    flaky_failures = [RuntimeError("telegram is down")] * 2

    async def ok(session: AsyncSession, event: Event) -> None:
        calls["ok"] += 1

    async def flaky(session: AsyncSession, event: Event) -> None:
        calls["flaky"] += 1
        if flaky_failures:
            raise flaky_failures.pop()

    dispatcher = Dispatcher()
    dispatcher.subscribe("ordering.order.*", "ok", ok)
    dispatcher.subscribe("ordering.order.placed", "flaky", flaky)
    dispatcher.subscribe("payments.payment.*", "other", ok)
    await emit(session_factory)

    assert await dispatcher.deliver_due(session_factory, NOW) == 1
    # Not due again until the backoff passes.
    assert await dispatcher.deliver_due(session_factory, NOW + timedelta(seconds=1)) == 0
    assert await dispatcher.deliver_due(session_factory, NOW + timedelta(seconds=3)) == 1
    assert await dispatcher.deliver_due(session_factory, NOW + timedelta(seconds=10)) == 1
    assert await dispatcher.deliver_due(session_factory, NOW + timedelta(hours=1)) == 0
    # The handler that succeeded the first time was not repeated (idempotent by event id).
    assert calls == {"ok": 1, "flaky": 3}
    async with session_factory() as session:
        event = (await session.execute(select(OutboxEvent))).scalar_one()
    assert event.processed_at is not None
    assert event.attempts == 2


async def test_backoff_is_capped() -> None:
    assert outbox.backoff(1) == timedelta(seconds=2)
    assert outbox.backoff(30) == outbox.MAX_BACKOFF


async def test_a_handler_database_error_is_contained(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from sqlalchemy import text

    async def broken(session: AsyncSession, event: Event) -> None:
        await session.execute(text("SELECT * FROM no_such_table"))

    async def ok(session: AsyncSession, event: Event) -> None:
        return None

    dispatcher = Dispatcher()
    dispatcher.subscribe("ordering.order.*", "broken", broken)
    dispatcher.subscribe("ordering.order.*", "ok", ok)
    await emit(session_factory)
    assert await dispatcher.deliver_due(session_factory, NOW) == 1
    async with session_factory() as session:
        event = (await session.execute(select(OutboxEvent))).scalar_one()
    assert event.processed_at is None
    assert event.last_error is not None and "broken" in event.last_error
