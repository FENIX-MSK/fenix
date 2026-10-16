from dataclasses import dataclass, field
from typing import Any

from aiogram.filters import CommandObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.modules.identity.models import IdentityUser
from fenix.platform.config import Settings
from fenix.telegram.handlers.start import (
    GREETING,
    INVITATION_INVALID,
    STAFF_GRANTED,
    build_start_keyboard,
    handle_start,
)


def test_start_keyboard_hidden_without_webapp_url() -> None:
    assert build_start_keyboard(Settings(webapp_url=None)) is None


def test_start_keyboard_opens_webapp() -> None:
    keyboard = build_start_keyboard(Settings(webapp_url="https://example.test"))
    assert keyboard is not None
    button = keyboard.inline_keyboard[0][0]
    assert button.web_app is not None
    assert button.web_app.url == "https://example.test"


@dataclass
class Sender:
    id: int = 42
    first_name: str = "Аня"
    last_name: str | None = None
    username: str | None = None
    is_bot: bool = False


@dataclass
class FakeMessage:
    from_user: Sender | None = field(default_factory=Sender)
    answers: list[tuple[str, Any]] = field(default_factory=list)

    async def answer(self, text: str, reply_markup: Any = None) -> None:
        self.answers.append((text, reply_markup))


async def start(
    factory: async_sessionmaker[AsyncSession],
    args: str | None,
    message: FakeMessage | None = None,
    **settings: str,
) -> FakeMessage:
    message = message or FakeMessage()
    await handle_start(
        message,  # type: ignore[arg-type]
        CommandObject(command="start", args=args),
        Settings(webapp_url="https://example.test", **settings),  # type: ignore[arg-type]
        factory,
    )
    return message


async def sources(factory: async_sessionmaker[AsyncSession]) -> list[str]:
    async with factory() as session:
        return list((await session.execute(select(IdentityUser.source))).scalars())


async def test_start_without_label(session_factory: async_sessionmaker[AsyncSession]) -> None:
    message = await start(session_factory, None)
    assert await sources(session_factory) == ["direct"]
    [(text, keyboard)] = message.answers
    assert text == GREETING
    assert keyboard.inline_keyboard[0][0].text == "Открыть меню"


async def test_start_with_label_then_another(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await start(session_factory, "qr_table")
    await start(session_factory, "promo")
    assert await sources(session_factory) == ["qr_table"]


async def test_start_with_malformed_label(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await start(session_factory, "../etc")
    assert await sources(session_factory) == ["direct"]


async def test_start_from_unknown_sender_only_answers(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    message = await start(session_factory, None, FakeMessage(from_user=None))
    assert await sources(session_factory) == []
    assert len(message.answers) == 1


async def test_bootstrap_by_username(seeded: async_sessionmaker[AsyncSession]) -> None:
    owner = FakeMessage(from_user=Sender(id=10, username="Owner"))
    message = await start(seeded, None, owner, bootstrap_staff_telegram_username="@owner")
    assert message.answers[0][0] == STAFF_GRANTED
    other = FakeMessage(from_user=Sender(id=11, username="owner2"))
    assert (await start(seeded, None, other, bootstrap_staff_telegram_username="owner")).answers[0][
        0
    ] == GREETING
    again = FakeMessage(from_user=Sender(id=12, username="owner"))
    # A second account with the same username after staff exists: ignored.
    assert (await start(seeded, None, again, bootstrap_staff_telegram_username="owner")).answers[0][
        0
    ] == GREETING


async def test_invitation_through_the_bot(seeded: async_sessionmaker[AsyncSession]) -> None:
    from datetime import UTC, datetime

    from fenix.modules.identity import api as identity
    from fenix.modules.locations import api as locations

    async with seeded() as session, session.begin():
        owner = await identity.ensure_user(
            session, platform=identity.Platform.TELEGRAM, external_id="1", first_name="Света"
        )
        location_id = await locations.get_default_location_id(session)
        assert location_id is not None
        await identity.bootstrap_first_staff(session, owner.id, location_id)
        token, _ = await identity.create_invitation(
            session, owner.id, location_id, datetime.now(UTC)
        )

    guest = FakeMessage(from_user=Sender(id=20))
    assert (await start(seeded, f"inv_{token}", guest)).answers[0][0] == STAFF_GRANTED
    late = FakeMessage(from_user=Sender(id=21))
    assert (await start(seeded, f"inv_{token}", late)).answers[0][0] == INVITATION_INVALID
    async with seeded() as session:
        sources = set((await session.execute(select(IdentityUser.source))).scalars())
    assert "staff_invite" in sources
    assert not any(source.startswith("inv_") for source in sources)
