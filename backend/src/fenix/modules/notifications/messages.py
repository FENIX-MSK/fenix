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


def address_text(payload: dict[str, Any]) -> str:
    address = payload.get("address") or {}
    parts = [f"корпус {address.get('house', '')}", f"кв. {address.get('apartment', '')}"]
    if address.get("entrance"):
        parts.append(f"подъезд {address['entrance']}")
    if address.get("floor"):
        parts.append(f"этаж {address['floor']}")
    return escape(", ".join(parts))


def guest_message(event: str, payload: dict[str, Any]) -> str | None:
    """What the guest is told about the event, or None when nothing is said (FR-16)."""
    status = payload["status"]
    if event in ("placed", "payment_confirmed") and status in ("new", "scheduled"):
        done = "запланирован" if status == "scheduled" else "оформлен"
        head = (
            f"Оплата прошла. Заказ {number(payload)} {done}."
            if event == "payment_confirmed"
            else f"Заказ {number(payload)} {done}."
        )
        details = []
        at = local_time(payload, "scheduled_for")
        if at:
            details.append(f"Будет готов к {at}.")
        if payload["fulfilment"] == "delivery":
            details.append(f"Доставка: {address_text(payload)}.")
        details.append(
            f"Итого: {rubles(payload['total'])}, {PAYMENT_TEXTS[payload['payment_method']]}."
        )
        if status == "new":
            details.append("Напишем, когда кафе примет заказ.")
        return f"{head}\n\n{lines_text(payload)}\n\n" + "\n".join(details)
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
    if event == "delivered":
        return f"Заказ {number(payload)} доставлен. Приятного аппетита."
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
    at = local_time(payload, "scheduled_for")
    kind = f"Предзаказ к {at}" if at else "Новый заказ"
    text = (
        f"{kind} {number(payload)} — {fulfilment}, {rubles(payload['total'])}\n"
        f"{lines_text(payload)}\n{payment}"
    )
    if payload["fulfilment"] == "delivery":
        text += f"\n🏠 {address_text(payload)}"
        if payload.get("change_from"):
            text += f"\nСдача с {rubles(payload['change_from'])}"
    if payload.get("comment"):
        text += f"\n💬 {escape(payload['comment'])}"
    return text
