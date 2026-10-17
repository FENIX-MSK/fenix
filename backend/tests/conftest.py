import asyncio
import importlib
import importlib.util
import os
import pkgutil
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Tests must never talk to the real bot; aiogram only validates the token format.
# Forced, not defaulted: test launch data is signed with this exact token.
os.environ["TELEGRAM_BOT_TOKEN"] = "123456:TEST-TOKEN"
os.environ["TELEGRAM_BOT_USERNAME"] = "fenix_test_bot"
os.environ.pop("BOOTSTRAP_STAFF_TELEGRAM_USERNAME", None)
# Tests must never touch the development database either.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://fenix:fenix@localhost:5432/fenix_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

BACKEND = Path(__file__).resolve().parent.parent

import fenix.modules  # noqa: E402
from fenix.platform.db import Base, create_engine, create_session_factory  # noqa: E402

# Register every module's tables in Base.metadata (same discovery as migrations/env.py).
for _module in pkgutil.iter_modules(fenix.modules.__path__):
    if importlib.util.find_spec(f"fenix.modules.{_module.name}.models"):
        importlib.import_module(f"fenix.modules.{_module.name}.models")
importlib.import_module("fenix.platform.outbox")


async def _create_database_if_missing(url: str) -> None:
    parsed = make_url(url)
    connection = await asyncpg.connect(
        user=parsed.username,
        password=parsed.password,
        host=parsed.host,
        port=parsed.port,
        database="postgres",
    )
    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", parsed.database
        )
        if not exists:
            await connection.execute(f'CREATE DATABASE "{parsed.database}"')
    finally:
        await connection.close()


@pytest.fixture(scope="session")
def migrated_database() -> Iterator[str]:
    """A test database brought to `head` by the real migrations, once per run."""
    asyncio.run(_create_database_if_missing(TEST_DATABASE_URL))
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        check=True,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
    )
    yield TEST_DATABASE_URL


@pytest.fixture
async def session_factory(
    migrated_database: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Empty tables for every test."""
    engine = create_engine(migrated_database)
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables} CASCADE"))
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    from init_data import sign_init_data

    return {"Authorization": f"tma {sign_init_data()}"}


@pytest.fixture
async def seeded(
    session_factory: async_sessionmaker[AsyncSession],
) -> async_sessionmaker[AsyncSession]:
    """The default location and the printed menu."""
    from fenix.modules.catalog import api as catalog
    from fenix.modules.locations import api as locations

    async with session_factory() as session, session.begin():
        await locations.seed_defaults(session)
        await catalog.seed_menu(session)
    return session_factory


STAFF_TELEGRAM_ID = 777


@pytest.fixture
async def staff_headers(seeded: async_sessionmaker[AsyncSession]) -> dict[str, str]:
    """Launch data of a staff member of the default location."""
    from init_data import sign_init_data

    from fenix.modules.identity import api as identity
    from fenix.modules.locations import api as locations

    async with seeded() as session, session.begin():
        user = await identity.ensure_user(
            session,
            platform=identity.Platform.TELEGRAM,
            external_id=str(STAFF_TELEGRAM_ID),
            first_name="Света",
        )
        location_id = await locations.get_default_location_id(session)
        assert location_id is not None
        await identity.bootstrap_first_staff(session, user.id, location_id)
    init_data = sign_init_data({"id": STAFF_TELEGRAM_ID, "first_name": "Света"})
    return {"Authorization": f"tma {init_data}"}


ALWAYS_OPEN = [{"weekday": d, "opens_at": "0:00", "closes_at": "0:00"} for d in range(7)]


async def make_open_always(factory: async_sessionmaker[AsyncSession]) -> None:
    from datetime import time

    from sqlalchemy import select as _select

    from fenix.modules.locations.models import Location, OpeningHours

    async with factory() as session, session.begin():
        location = (await session.execute(_select(Location))).scalar_one()
        # Update rows in place: replacing them would insert before deleting and clash
        # with the unique (location, weekday).
        existing = {row.weekday: row for row in location.opening_hours}
        for weekday in range(7):
            row = existing.get(weekday) or OpeningHours(weekday=weekday)
            row.opens_at = row.closes_at = time(0)
            if weekday not in existing:
                location.opening_hours.append(row)


@pytest.fixture
async def ready_guest(seeded: async_sessionmaker[AsyncSession]) -> async_sessionmaker[AsyncSession]:
    """An always-open cafe and a guest (id 42) with a phone and consent."""
    from datetime import UTC, datetime

    from fenix.modules.identity import api as identity

    await make_open_always(seeded)
    async with seeded() as session, session.begin():
        user = await identity.ensure_user(
            session, platform=identity.Platform.TELEGRAM, external_id="42", first_name="Аня"
        )
        await identity.update_contact(
            session, user.id, phone="+79991234567", consent=True, now=datetime.now(UTC)
        )
    return seeded
