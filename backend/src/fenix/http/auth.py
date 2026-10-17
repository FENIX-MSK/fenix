"""Every /api/v1 request is made on behalf of the messenger user who opened the Mini App."""

import uuid
from typing import Annotated

import structlog
from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from fenix.http.deps import SessionDep, SettingsDep
from fenix.modules.identity import api as identity
from fenix.modules.locations import api as locations
from fenix.platform.config import Settings
from fenix.platform.errors import ApiError
from fenix.platform.messenger_auth import InvalidInitDataError, verify_telegram_init_data

log = structlog.get_logger()

SCHEME = "tma "


def _unauthorized() -> ApiError:
    return ApiError(401, "unauthorized", "Valid Telegram Mini App launch data is required")


async def current_user(
    session: SessionDep,
    settings: SettingsDep,
    authorization: Annotated[str | None, Header()] = None,
) -> identity.User:
    if not authorization or not authorization.startswith(SCHEME):
        raise _unauthorized()
    user = await authenticate(session, settings, authorization.removeprefix(SCHEME))
    structlog.contextvars.bind_contextvars(user_id=str(user.id))
    return user


async def authenticate(session: AsyncSession, settings: Settings, init_data: str) -> identity.User:
    """The user behind signed launch data (AD-7); raises 401 otherwise."""
    try:
        launch = verify_telegram_init_data(
            init_data, settings.telegram_bot_token.get_secret_value()
        )
    except InvalidInitDataError as exc:
        # The reason only; the launch data itself carries personal data.
        log.info("http.auth.rejected", reason=str(exc))
        raise _unauthorized() from exc

    user = await identity.ensure_user(
        session,
        platform=identity.Platform.TELEGRAM,
        external_id=launch.external_id,
        first_name=launch.first_name,
        last_name=launch.last_name,
        username=launch.username,
        source=launch.start_param,
    )
    return user


# FastAPI resolves a dependency once per request, so the router-wide check and a
# route's `user: CurrentUser` parameter share one verification and one lookup.
CurrentUser = Annotated[identity.User, Depends(current_user)]


async def current_location_id(session: SessionDep) -> uuid.UUID:
    location_id = await locations.get_default_location_id(session)
    if location_id is None:
        raise ApiError(404, "location_not_found", "No location is configured")
    return location_id


LocationIdDep = Annotated[uuid.UUID, Depends(current_location_id)]


async def current_staff(
    user: CurrentUser, session: SessionDep, location_id: LocationIdDep
) -> identity.User:
    """Staff routes are checked on the server on every request (AD-7)."""
    if not await identity.is_staff(session, user.id, location_id):
        raise ApiError(403, "forbidden", "This section is for the cafe staff")
    return user


CurrentStaff = Annotated[identity.User, Depends(current_staff)]
