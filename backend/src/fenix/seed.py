"""Initial data and storage for a fresh stand. Safe to run on every deploy: what exists is kept.

Usage: fenix-seed
"""

import asyncio
import time

import structlog

from fenix.modules.catalog import api as catalog
from fenix.modules.locations import api as locations
from fenix.platform.config import Settings, get_settings
from fenix.platform.db import create_engine, create_session_factory
from fenix.platform.logging import configure_logging
from fenix.platform.storage import ensure_bucket

log = structlog.get_logger()


def init_storage(settings: Settings, attempts: int = 30) -> None:
    """Garage may still be starting when the migrate service runs: retry for a minute."""
    for attempt in range(1, attempts + 1):
        try:
            log.info("seed.storage", changed=ensure_bucket(settings))
            return
        except (OSError, RuntimeError, KeyError) as exc:
            if attempt == attempts:
                raise
            log.info("seed.storage.waiting", error=str(exc), attempt=attempt)
            time.sleep(2)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json=settings.is_production)
    init_storage(settings)
    engine = create_engine(settings.database_url)
    try:
        async with create_session_factory(engine)() as session, session.begin():
            log.info("seed.locations", created=await locations.seed_defaults(session))
            log.info("seed.catalog", created=await catalog.seed_menu(session))
            location_id = await locations.get_default_location_id(session)
            if location_id is not None:
                created = await catalog.seed_promotions(session, location_id)
                log.info("seed.promotions", created=created)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
