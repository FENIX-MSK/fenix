from dataclasses import dataclass, field
from typing import Any

from aiogram.filters import CommandObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_start import FakeMessage, Sender

from fenix.modules.locations import api as locations
from fenix.modules.notifications import api as notifications
from fenix.platform.config import Settings
from fenix.telegram.handlers.staff_chat import (
    BOUND,
    GROUPS_ONLY,
    NOT_STAFF,
    REPLACED,
    handle_bind,
    handle_migration,
)
from fenix.telegram.handlers.start import ORDER_NOT_STAFF, handle_start


@dataclass
class Chat:
    id: int = -100500
    type: str = "supergroup"
    title: str | None = "Кухня"


@dataclass
class GroupMessage(FakeMessage):
    chat: Chat = field(default_factory=Chat)
    migrate_to_chat_id: int | None = None


async def bound_chat(factory: async_sessionmaker[AsyncSession]) -> Any:
    async with factory() as session:
        location_id = await locations.get_default_location_id(session)
        assert location_id
        return await notifications.get_staff_chat(session, location_id)


STAFF = Sender(id=777, first_name="Света")


async def test_staff_binds_the_group(
    seeded: async_sessionmaker[AsyncSession], staff_headers: dict[str, str]
) -> None:
    message = GroupMessage(from_user=STAFF)
    await handle_bind(message, seeded)  # type: ignore[arg-type]
    assert message.answers[0][0] == BOUND
    chat = await bound_chat(seeded)
    assert (chat.platform, chat.chat_id, chat.title) == ("telegram", "-100500", "Кухня")

    other = GroupMessage(from_user=STAFF, chat=Chat(id=-200, title="Новая кухня"))
    await handle_bind(other, seeded)  # type: ignore[arg-type]
    assert other.answers[0][0] == REPLACED
    assert (await bound_chat(seeded)).chat_id == "-200"


async def test_guest_cannot_bind(
    seeded: async_sessionmaker[AsyncSession], staff_headers: dict[str, str]
) -> None:
    message = GroupMessage(from_user=Sender(id=42))
    await handle_bind(message, seeded)  # type: ignore[arg-type]
    assert message.answers[0][0] == NOT_STAFF
    assert await bound_chat(seeded) is None


async def test_bind_in_private_chat_explains(seeded: async_sessionmaker[AsyncSession]) -> None:
    message = GroupMessage(from_user=STAFF, chat=Chat(id=777, type="private", title=None))
    await handle_bind(message, seeded)  # type: ignore[arg-type]
    assert message.answers[0][0] == GROUPS_ONLY


async def test_binding_follows_supergroup_migration(
    seeded: async_sessionmaker[AsyncSession], staff_headers: dict[str, str]
) -> None:
    await handle_bind(GroupMessage(from_user=STAFF, chat=Chat(id=-5, type="group")), seeded)  # type: ignore[arg-type]
    await handle_migration(
        GroupMessage(chat=Chat(id=-5, type="group"), migrate_to_chat_id=-1005),  # type: ignore[arg-type]
        seeded,
    )
    assert (await bound_chat(seeded)).chat_id == "-1005"


async def test_order_link_opens_the_board_for_staff(
    seeded: async_sessionmaker[AsyncSession], staff_headers: dict[str, str]
) -> None:
    message = FakeMessage(from_user=STAFF)
    await handle_start(
        message,  # type: ignore[arg-type]
        CommandObject(command="start", args="order_0199"),
        Settings(webapp_url="https://example.test"),  # type: ignore[call-arg]
        seeded,
    )
    keyboard = message.answers[0][1]
    assert keyboard.inline_keyboard[0][0].web_app.url == ("https://example.test?order=0199&staff=1")


async def test_order_link_is_refused_to_guests(seeded: async_sessionmaker[AsyncSession]) -> None:
    message = FakeMessage(from_user=Sender(id=42))
    await handle_start(
        message,  # type: ignore[arg-type]
        CommandObject(command="start", args="order_0199"),
        Settings(webapp_url="https://example.test"),  # type: ignore[call-arg]
        seeded,
    )
    assert message.answers[0][0] == ORDER_NOT_STAFF
