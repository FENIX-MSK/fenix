import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import structlog
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from fenix.api import health
from fenix.config import BotMode, Settings, get_settings
from fenix.db import create_engine, create_session_factory
from fenix.logging import configure_logging
from fenix.telegram import webhook
from fenix.telegram.bot import configure_menu_button, create_bot, create_dispatcher

log = structlog.get_logger()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json=settings.is_production)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings.database_url)
        app.state.session_factory = create_session_factory(engine)

        bot = create_bot(settings)
        app.state.bot = bot
        app.state.dispatcher = create_dispatcher(settings)
        app.state.webhook_secret = (
            settings.telegram_webhook_secret.get_secret_value()
            if settings.telegram_webhook_secret
            else None
        )
        # Telegram may be unreachable (blocked egress, outage); the API must still start.
        webhook_task = (
            asyncio.create_task(_register_webhook(app, settings))
            if settings.telegram_bot_mode is BotMode.WEBHOOK
            else None
        )

        log.info(
            "app.started", environment=settings.environment, bot_mode=settings.telegram_bot_mode
        )
        try:
            yield
        finally:
            if webhook_task:
                webhook_task.cancel()
                with suppress(asyncio.CancelledError):
                    await webhook_task
            await bot.session.close()
            await engine.dispose()

    app = FastAPI(title="Fenix API", lifespan=lifespan)
    app.include_router(health.router, prefix="/api")
    app.include_router(webhook.router)
    Instrumentator(excluded_handlers=["/metrics", "/api/health"]).instrument(app).expose(
        app, include_in_schema=False
    )
    return app


WEBHOOK_RETRY_MAX_DELAY = 300.0


async def _register_webhook(app: FastAPI, settings: Settings) -> None:
    """Register the webhook, retrying with backoff until Telegram is reachable."""
    if not settings.public_base_url or not app.state.webhook_secret:
        log.error(
            "telegram.webhook.misconfigured", missing="PUBLIC_BASE_URL/TELEGRAM_WEBHOOK_SECRET"
        )
        return

    delay = 5.0
    while True:
        try:
            await app.state.bot.set_webhook(
                url=settings.public_base_url.rstrip("/") + webhook.WEBHOOK_PATH,
                secret_token=app.state.webhook_secret,
                drop_pending_updates=False,
            )
            await configure_menu_button(app.state.bot, settings)
        except Exception as exc:
            log.warning("telegram.webhook.register_failed", error=str(exc), retry_in=delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, WEBHOOK_RETRY_MAX_DELAY)
        else:
            log.info("telegram.webhook.registered")
            return
