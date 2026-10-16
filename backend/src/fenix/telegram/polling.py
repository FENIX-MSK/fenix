"""Bot service: receives updates with long polling in every environment (AD-8)."""

import asyncio

import structlog

from fenix.platform.config import get_settings
from fenix.platform.logging import configure_logging
from fenix.telegram.bot import configure_menu_button, create_bot, create_dispatcher

log = structlog.get_logger()


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json=settings.is_production)
    bot = create_bot(settings)
    dispatcher = create_dispatcher(settings)
    await bot.delete_webhook(drop_pending_updates=True)
    await configure_menu_button(bot, settings)
    log.info("bot.polling.start")
    await dispatcher.start_polling(bot)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
