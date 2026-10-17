"""Bot service: receives updates with long polling in every environment (AD-8)."""

import asyncio

import structlog

from fenix.platform import metrics
from fenix.platform.config import get_settings
from fenix.platform.db import create_engine, create_session_factory
from fenix.platform.logging import configure_logging
from fenix.telegram.bot import configure_menu_button, create_bot, create_dispatcher

log = structlog.get_logger()


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json=settings.is_production)
    engine = create_engine(settings.database_url)
    bot = create_bot(settings)
    dispatcher = create_dispatcher(settings, create_session_factory(engine))
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await configure_menu_button(bot, settings)
        metrics.serve(metrics.BOT_PORT)
        metrics.BOT_UP.set(1)
        log.info("bot.polling.start")
        await dispatcher.start_polling(bot)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
