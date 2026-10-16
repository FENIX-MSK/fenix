from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.platform.config import Settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One transaction per request: committed on success, rolled back on any error."""
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session, session.begin():
        yield session


def get_settings_from_app(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


# scope="function": the transaction closes before the response is sent, so a failed
# commit becomes a 500 instead of a 200 for data that was never stored.
SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]
SettingsDep = Annotated[Settings, Depends(get_settings_from_app)]
