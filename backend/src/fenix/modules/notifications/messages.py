"""Message texts rendered from event payloads alone (AD-4). HTML: user data is escaped."""

from datetime import datetime
from html import escape
from typing import Any
from zoneinfo import ZoneInfo

PAYMENT_TEXTS = {
    "online": "оплачен онлайн",
    "cash": "оплата наличными на кассе",
    "card": "оплата картой на кассе",
}
FULFILMENT_TEXTS = {"pickup": "самовывоз", "delivery": "доставка"}


def rubles(kopecks: int) -> str:
    return f"{kopecks // 100:,}".replace(",", " ") + " ₽"


def local_time(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if not value:
        return None
    moment = datetime.fromisoformat(value).astimezone(ZoneInfo(payload["timezone"]))
    return f"{moment.hour}:{moment.minute:02d}"


def lines_text(payload: dict[str, Any]) -> str:
    rows = []
    for line in payload["lines"]:
        extras = f" ({escape(', '.join(line['modifier_names']))})" if line["modifier_names"] else ""
        quantity = f" × {line['quantity']}" if line["quantity"] > 1 else ""
        rows.append(f"• {escape(line['title'])}{extras}{quantity}")
    return "\n".join(rows)


def number(payload: dict[str, Any]) -> str:
    return f"<b>{escape(payload['number'])}</b>"


def guest_message(event: str, payload: dict[str, Any]) -> str | None:
    """What the guest is told about the event, or None when nothing is said (FR-16)."""
    status = payload["status"]
    if event in ("placed", "payment_confirmed") and status == "new":
        head = (
            f"Оплата прошла. Заказ {number(payload)} оформлен."
            if event == "payment_confirmed"
            else f"Заказ {number(payload)} оформлен."
        )
        return (
            f"{head}\n\n{lines_text(payload)}\n\n"
            f"Итого: {rubles(payload['total'])}, {PAYMENT_TEXTS[payload['payment_method']]}.\n"
            "Напишем, когда кафе примет заказ."
        )
    if event == "accepted":
        at = local_time(payload, "ready_at")
        when = f" Будет готов к {at}." if at else ""
        return f"Заказ {number(payload)} принят.{when}"
    if event == "ready":
        if payload["fulfilment"] == "pickup":
            return f"Заказ {number(payload)} готов — ждём вас у кассы."
        return None
    if event == "dispatched":
        return f"Заказ {number(payload)} уже едет к вам."
    if event == "cancelled":
        # The staff's reason stays inside the cafe (FR-22).
        if payload.get("unpaid_timeout"):
            text = f"Заказ {number(payload)} отменён: оплата не поступила вовремя."
        else:
            text = f"К сожалению, заказ {number(payload)} отменён."
        if payload.get("refunded"):
            text += " Деньги за онлайн-оплату вернутся."
        return text
    return None


def staff_new_order(payload: dict[str, Any]) -> str:
    payment = PAYMENT_TEXTS[payload["payment_method"]]
    fulfilment = FULFILMENT_TEXTS.get(payload["fulfilment"], payload["fulfilment"])
    text = (
        f"Новый заказ {number(payload)} — {fulfilment}, {rubles(payload['total'])}\n"
        f"{lines_text(payload)}\n{payment}"
    )
    if payload.get("comment"):
        text += f"\n💬 {escape(payload['comment'])}"
    return text
