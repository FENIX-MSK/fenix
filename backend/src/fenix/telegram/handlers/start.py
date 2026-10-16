from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.modules.identity import api as identity
from fenix.platform.config import Settings

GREETING = (
    "Добро пожаловать в «Феникс бистро»! "
    "Здесь можно посмотреть меню и заказать с собой или с доставкой."
)


def build_start_keyboard(settings: Settings) -> InlineKeyboardMarkup | None:
    if not settings.webapp_url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть меню", web_app=WebAppInfo(url=settings.webapp_url))]
        ]
    )


async def handle_start(
    message: Message,
    command: CommandObject,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    sender = message.from_user
    if sender is not None and not sender.is_bot:
        async with session_factory() as session, session.begin():
            await identity.ensure_user(
                session,
                platform=identity.Platform.TELEGRAM,
                external_id=str(sender.id),
                first_name=sender.first_name,
                last_name=sender.last_name,
                username=sender.username,
                # `/start qr_table` from a t.me/<bot>?start=qr_table link.
                source=command.args,
            )
    await message.answer(GREETING, reply_markup=build_start_keyboard(settings))


def create_router() -> Router:
    # A router can belong to one dispatcher only, so build a fresh one per dispatcher.
    router = Router(name="start")
    router.message.register(handle_start, CommandStart())
    return router
