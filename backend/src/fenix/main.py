from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.types import Lifespan

from fenix.http import health
from fenix.http.router import api_v1
from fenix.platform.config import Settings, get_settings
from fenix.platform.db import create_engine, create_session_factory
from fenix.platform.errors import EXCEPTION_HANDLERS
from fenix.platform.logging import configure_logging
from fenix.platform.storage import S3Storage

log = structlog.get_logger()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json=settings.is_production)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings.database_url)
        app.state.settings = settings
        app.state.media_storage = S3Storage(settings)
        app.state.session_factory = create_session_factory(engine)
        log.info("app.started", environment=settings.environment)
        try:
            yield
        finally:
            await engine.dispose()

    return build_app(lifespan=lifespan)


def build_app(lifespan: Lifespan[FastAPI] | None = None) -> FastAPI:
    """Assemble routes and handlers. Needs no settings, so the OpenAPI export can use it."""
    app = FastAPI(title="Fenix API", lifespan=lifespan, exception_handlers=EXCEPTION_HANDLERS)
    app.include_router(health.router, prefix="/api")
    app.include_router(api_v1)
    Instrumentator(excluded_handlers=["/metrics", "/api/health"]).instrument(app).expose(
        app, include_in_schema=False
    )
    return app
