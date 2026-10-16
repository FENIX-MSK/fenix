from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import MenuButtonWebApp, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.platform.config import Settings
from fenix.telegram.handlers import start


def create_bot(settings: Settings) -> Bot:
    proxy = settings.telegram_proxy_url
    return Bot(
        token=settings.telegram_bot_token.get_secret_value(),
        session=AiohttpSession(proxy=proxy.get_secret_value()) if proxy else None,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> Dispatcher:
    # Workflow data: handlers receive these by parameter name.
    dispatcher = Dispatcher(settings=settings, session_factory=session_factory)
    dispatcher.include_router(start.create_router())
    return dispatcher


async def configure_menu_button(bot: Bot, settings: Settings) -> None:
    """Point the chat menu button at the Mini App, when one is configured."""
    if settings.webapp_url:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Меню", web_app=WebAppInfo(url=settings.webapp_url))
        )
