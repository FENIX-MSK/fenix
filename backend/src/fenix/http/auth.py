"""Every /api/v1 request is made on behalf of the messenger user who opened the Mini App."""

from typing import Annotated

import structlog
from fastapi import Depends, Header

from fenix.http.deps import SessionDep, SettingsDep
from fenix.modules.identity import api as identity
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
    try:
        launch = verify_telegram_init_data(
            authorization.removeprefix(SCHEME),
            settings.telegram_bot_token.get_secret_value(),
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
    structlog.contextvars.bind_contextvars(user_id=str(user.id))
    return user


# FastAPI resolves a dependency once per request, so the router-wide check and a
# route's `user: CurrentUser` parameter share one verification and one lookup.
CurrentUser = Annotated[identity.User, Depends(current_user)]
