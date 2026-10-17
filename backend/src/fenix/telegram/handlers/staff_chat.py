"""`/bind` in a group: the group becomes the location's staff chat (FR-24)."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.modules.identity import api as identity
from fenix.modules.locations import api as locations
from fenix.modules.notifications import api as notifications

BOUND = "Готово: сюда будут приходить новые заказы."
REPLACED = "Готово: новые заказы теперь приходят сюда, а не в прежний чат."
NOT_STAFF = "Привязать чат может только сотрудник кафе."
GROUPS_ONLY = "Команда /bind работает в группе: добавьте бота в служебный чат и отправьте её там."


async def handle_bind(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    sender = message.from_user
    if message.chat.type not in ("group", "supergroup"):
        await message.answer(GROUPS_ONLY)
        return
    if sender is None or sender.is_bot:
        return
    async with session_factory() as session, session.begin():
        user = await identity.find_user(session, identity.Platform.TELEGRAM, str(sender.id))
        location_id = await locations.get_default_location_id(session)
        if (
            user is None
            or location_id is None
            or not await identity.is_staff(session, user.id, location_id)
        ):
            await message.answer(NOT_STAFF)
            return
        replaced = await notifications.bind_staff_chat(
            session,
            location_id,
            platform="telegram",
            chat_id=str(message.chat.id),
            title=message.chat.title or "",
            user_id=user.id,
        )
    await message.answer(REPLACED if replaced else BOUND)


async def handle_migration(
    message: Message, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """A group upgraded to a supergroup gets a new id; keep the binding."""
    new_id = message.migrate_to_chat_id
    if new_id is None:
        return
    async with session_factory() as session, session.begin():
        location_id = await locations.get_default_location_id(session)
        if location_id is None:
            return
        chat = await notifications.get_staff_chat(session, location_id)
        if chat and chat.chat_id == str(message.chat.id):
            await notifications.bind_staff_chat(
                session,
                location_id,
                platform="telegram",
                chat_id=str(new_id),
                title=chat.title,
                user_id=None,
            )


def create_router() -> Router:
    router = Router(name="staff_chat")
    router.message.register(handle_bind, Command("bind"))
    router.message.register(handle_migration, F.migrate_to_chat_id)
    return router
