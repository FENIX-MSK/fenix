"""The messenger as seen by modules (AD-8): no SDK types cross this line."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Button:
    text: str
    # Exactly one of these: a plain link, or the Mini App opened at this URL.
    url: str | None = None
    web_app_url: str | None = None


class Undeliverable(Exception):
    """The chat will never accept the message (the user blocked the bot, the group is gone).

    Retrying cannot help, so handlers drop the message instead of retrying forever."""


class MessengerGateway(Protocol):
    async def send(
        self, platform: str, chat_id: str, text: str, buttons: list[Button] | None = None
    ) -> None:
        """Send an HTML-formatted message. Raises Undeliverable, or anything else to retry."""
        ...
