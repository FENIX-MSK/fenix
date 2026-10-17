"""Outbox subscribers that tell people about orders (FR-16, FR-24)."""

import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.notifications import messages, staff_chat
from fenix.modules.notifications.gateway import Button, MessengerGateway, Undeliverable
from fenix.platform.outbox import Event, Handler, Subscription

log = structlog.get_logger()

# Events that bring an order to the kitchen's attention.
NEW_FOR_STAFF = frozenset({"placed", "payment_confirmed", "released"})


@dataclass(frozen=True, slots=True)
class Links:
    """Where buttons lead; built by the adapter that knows the messenger."""

    webapp_url: str | None
    # t.me/<bot>?start=… for a button in a group, where Mini App buttons are not allowed.
    bot_username: str | None


def order_event(event: Event) -> str:
    return event.name.removeprefix("ordering.order.")


def guest_handler(gateway: MessengerGateway, links: Links) -> Handler:
    async def handle(session: AsyncSession, event: Event) -> None:
        payload = event.payload
        text = messages.guest_message(order_event(event), payload)
        customer = payload["customer"]
        if text is None or not customer.get("external_id"):
            return
        buttons = (
            [Button("Открыть заказ", web_app_url=f"{links.webapp_url}?order={payload['order_id']}")]
            if links.webapp_url
            else None
        )
        try:
            await gateway.send(customer["platform"], customer["external_id"], text, buttons)
        except Undeliverable as exc:
            # The guest blocked the bot: the order goes on, the message is dropped.
            log.info(
                "notifications.guest_undeliverable", order_id=payload["order_id"], error=str(exc)
            )

    return handle


def staff_handler(gateway: MessengerGateway, links: Links) -> Handler:
    async def handle(session: AsyncSession, event: Event) -> None:
        payload = event.payload
        if order_event(event) not in NEW_FOR_STAFF or payload["status"] != "new":
            return
        chat = await staff_chat.get(session, uuid.UUID(payload["location_id"]))
        if chat is None:
            log.warning("notifications.no_staff_chat", location_id=payload["location_id"])
            return
        buttons = (
            [
                Button(
                    "Открыть заказ",
                    url=f"https://t.me/{links.bot_username}?start=order_{payload['order_id']}",
                )
            ]
            if links.bot_username
            else None
        )
        try:
            await gateway.send(
                chat.platform, chat.chat_id, messages.staff_new_order(payload), buttons
            )
        except Undeliverable as exc:
            log.warning(
                "notifications.staff_chat_undeliverable", chat_id=chat.chat_id, error=str(exc)
            )

    return handle


def subscriptions(gateway: MessengerGateway, links: Links) -> list[Subscription]:
    return [
        Subscription("ordering.order.*", "notifications.guest", guest_handler(gateway, links)),
        Subscription("ordering.order.*", "notifications.staff", staff_handler(gateway, links)),
    ]
