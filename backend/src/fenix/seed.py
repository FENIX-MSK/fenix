"""Initial data for a fresh database. Safe to run on every deploy: modules skip what exists.

Usage: fenix-seed
"""

import asyncio

import structlog

from fenix.modules.locations import api as locations
from fenix.platform.config import get_settings
from fenix.platform.db import create_engine, create_session_factory
from fenix.platform.logging import configure_logging

log = structlog.get_logger()


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json=settings.is_production)
    engine = create_engine(settings.database_url)
    try:
        async with create_session_factory(engine)() as session, session.begin():
            created = await locations.seed_defaults(session)
            log.info("seed.locations", created=created)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
