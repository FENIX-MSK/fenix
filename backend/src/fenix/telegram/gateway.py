"""`MessengerGateway` over the Telegram Bot API (AD-8)."""

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from fenix.modules.notifications import api as notifications


def keyboard(buttons: list[notifications.Button] | None) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    rows = [
        [
            InlineKeyboardButton(
                text=button.text,
                url=button.url,
                web_app=WebAppInfo(url=button.web_app_url) if button.web_app_url else None,
            )
        ]
        for button in buttons
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


class TelegramGateway:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def send(
        self,
        platform: str,
        chat_id: str,
        text: str,
        buttons: list[notifications.Button] | None = None,
    ) -> None:
        if platform != "telegram":
            raise notifications.Undeliverable(f"no gateway for {platform}")
        try:
            await self.bot.send_message(int(chat_id), text, reply_markup=keyboard(buttons))
        except TelegramForbiddenError as exc:
            # Blocked by the user or removed from the group: retrying cannot help.
            raise notifications.Undeliverable(str(exc)) from exc
        except TelegramBadRequest as exc:
            if "chat not found" in str(exc).lower():
                raise notifications.Undeliverable(str(exc)) from exc
            raise
