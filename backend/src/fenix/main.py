from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

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
        if settings.telegram_bot_mode is BotMode.WEBHOOK:
            await _register_webhook(app, settings)

        log.info(
            "app.started", environment=settings.environment, bot_mode=settings.telegram_bot_mode
        )
        try:
            yield
        finally:
            await bot.session.close()
            await engine.dispose()

    app = FastAPI(title="Fenix API", lifespan=lifespan)
    app.include_router(health.router, prefix="/api")
    app.include_router(webhook.router)
    Instrumentator(excluded_handlers=["/metrics", "/api/health"]).instrument(app).expose(
        app, include_in_schema=False
    )
    return app


async def _register_webhook(app: FastAPI, settings: Settings) -> None:
    if not settings.public_base_url or not app.state.webhook_secret:
        raise RuntimeError("Webhook mode needs PUBLIC_BASE_URL and TELEGRAM_WEBHOOK_SECRET")
    await app.state.bot.set_webhook(
        url=settings.public_base_url.rstrip("/") + webhook.WEBHOOK_PATH,
        secret_token=app.state.webhook_secret,
        drop_pending_updates=False,
    )
    await configure_menu_button(app.state.bot, settings)
