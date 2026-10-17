from typing import Any

from fenix.modules.notifications.messages import guest_message, rubles, staff_new_order


def payload(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "order_id": "o1",
        "location_id": "l1",
        "number": "#007",
        "status": "new",
        "fulfilment": "pickup",
        "payment_method": "cash",
        "total": 123400,
        "comment": "<b>без лука</b>",
        "ready_at": "2026-10-17T11:35:00+00:00",
        "timezone": "Europe/Moscow",
        "lines": [{"title": "Ролл <Филадельфия>", "modifier_names": ["Соус"], "quantity": 2}],
        "customer": {"platform": "telegram", "external_id": "42", "name": "Аня"},
    }
    return base | changes


def test_rubles() -> None:
    assert rubles(123400) == "1 234 ₽"


def test_placed_lists_the_order_and_escapes_html() -> None:
    text = guest_message("placed", payload())
    assert text is not None
    assert text.startswith("Заказ <b>#007</b> оформлен.")
    assert "Ролл &lt;Филадельфия&gt; (Соус) × 2" in text
    assert "1 234 ₽, оплата наличными на кассе" in text


def test_unpaid_online_order_says_nothing_yet() -> None:
    assert guest_message("placed", payload(status="pending_payment")) is None


def test_accepted_shows_local_ready_time() -> None:
    assert (
        guest_message("accepted", payload())
        == "Кафе приняло заказ <b>#007</b>. Будет готов к 14:35."
    )


def test_cancel_never_shows_the_reason() -> None:
    text = guest_message("cancelled", payload(refunded=True))
    assert text == (
        "Заказ <b>#007</b> отменён. Деньги вернутся тем же способом, которым вы платили."
    )


def test_quiet_events() -> None:
    assert guest_message("cooking_started", payload()) is None
    assert guest_message("handed_over", payload()) is None


def test_staff_message_escapes_comment() -> None:
    text = staff_new_order(payload())
    assert text.startswith("Новый заказ <b>#007</b> — самовывоз, 1 234 ₽")
    assert "&lt;b&gt;без лука&lt;/b&gt;" in text
