from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from fenix.platform.config import Settings

GREETING = (
    "Добро пожаловать в <b>Феникс бистро</b>!\n\n"
    "Здесь можно посмотреть меню, собрать заказ и забрать его без очереди."
)


def build_start_keyboard(settings: Settings) -> InlineKeyboardMarkup | None:
    if not settings.webapp_url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть меню", web_app=WebAppInfo(url=settings.webapp_url))]
        ]
    )


async def handle_start(message: Message, settings: Settings) -> None:
    await message.answer(GREETING, reply_markup=build_start_keyboard(settings))


def create_router() -> Router:
    # A router can belong to one dispatcher only, so build a fresh one per dispatcher.
    router = Router(name="start")
    router.message.register(handle_start, CommandStart())
    return router
