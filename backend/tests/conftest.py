import asyncio
import os
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
# Tests must never touch the development database either.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://fenix:fenix@localhost:5432/fenix_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

BACKEND = Path(__file__).resolve().parent.parent

# Register every module's tables in Base.metadata.
import fenix.modules.identity.models  # noqa: E402
import fenix.modules.locations.models  # noqa: E402, F401
from fenix.platform.db import Base, create_engine, create_session_factory  # noqa: E402


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
