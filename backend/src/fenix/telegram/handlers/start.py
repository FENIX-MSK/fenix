from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.modules.identity import api as identity
from fenix.modules.locations import api as locations
from fenix.platform.config import Settings

GREETING = (
    "Добро пожаловать в «Феникс бистро»! "
    "Здесь можно посмотреть меню и заказать с собой или с доставкой."
)
STAFF_GRANTED = "Готово, у вас есть доступ к разделу персонала."
INVITATION_INVALID = "Приглашение недействительно — попросите коллегу прислать новое."
# Guests who arrive through a staff invitation are not a marketing source.
INVITATION_SOURCE = "staff_invite"


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
    if sender is None or sender.is_bot:
        await message.answer(GREETING, reply_markup=build_start_keyboard(settings))
        return

    payload = command.args or ""
    invitation = (
        payload.removeprefix(identity.INVITATION_PREFIX)
        if payload.startswith(identity.INVITATION_PREFIX)
        else None
    )
    reply = GREETING
    async with session_factory() as session, session.begin():
        user = await identity.ensure_user(
            session,
            platform=identity.Platform.TELEGRAM,
            external_id=str(sender.id),
            first_name=sender.first_name,
            last_name=sender.last_name,
            username=sender.username,
            # `/start qr_table` from a t.me/<bot>?start=qr_table link.
            source=INVITATION_SOURCE if invitation is not None else payload or None,
        )
        if invitation is not None:
            accepted = await identity.accept_invitation(session, invitation, user.id)
            reply = STAFF_GRANTED if accepted else INVITATION_INVALID
        elif _is_bootstrap_user(settings, sender.username):
            location_id = await locations.get_default_location_id(session)
            if location_id is not None and await identity.bootstrap_first_staff(
                session, user.id, location_id
            ):
                reply = STAFF_GRANTED
    await message.answer(reply, reply_markup=build_start_keyboard(settings))


def _is_bootstrap_user(settings: Settings, username: str | None) -> bool:
    expected = settings.bootstrap_staff_telegram_username
    return bool(expected and username and username.lower() == expected.lstrip("@").lower())


def create_router() -> Router:
    # A router can belong to one dispatcher only, so build a fresh one per dispatcher.
    router = Router(name="start")
    router.message.register(handle_start, CommandStart())
    return router
