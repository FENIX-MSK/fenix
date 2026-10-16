import secrets
from typing import Annotated

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import APIRouter, Header, HTTPException, Request, status

router = APIRouter(tags=["telegram"])

WEBHOOK_PATH = "/telegram/webhook"


@router.post(WEBHOOK_PATH, include_in_schema=False)
async def telegram_webhook(
    request: Request,
    secret_token: Annotated[str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
) -> dict[str, bool]:
    expected: str | None = request.app.state.webhook_secret
    if (
        expected is None
        or secret_token is None
        or not secrets.compare_digest(secret_token, expected)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)

    bot: Bot = request.app.state.bot
    dispatcher: Dispatcher = request.app.state.dispatcher
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dispatcher.feed_update(bot, update)
    return {"ok": True}
