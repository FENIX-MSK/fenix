"""Public API of `ordering`: functions and DTOs, the only import surface for other modules."""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.ordering import cart, orders
from fenix.modules.ordering.cart import CartError, CartLine, CartView
from fenix.modules.ordering.orders import (
    ACTIVE,
    FINAL,
    SYSTEM,
    TRANSITIONS,
    Actor,
    LogEntry,
    OrderError,
    OrderLine,
    OrderView,
    PaymentMethod,
)
from fenix.platform.outbox import Event, Subscription

__all__ = [
    "ACTIVE",
    "FINAL",
    "SYSTEM",
    "TRANSITIONS",
    "Actor",
    "CartError",
    "CartLine",
    "CartView",
    "LogEntry",
    "OrderError",
    "OrderLine",
    "OrderView",
    "PaymentMethod",
    "add_to_cart",
    "cancel_unpaid",
    "get_order",
    "list_orders",
    "overdue_unpaid",
    "place_order",
    "remove_from_cart",
    "set_cart_quantity",
    "subscriptions",
    "transition",
    "view_cart",
]


async def view_cart(session: AsyncSession, user_id: uuid.UUID, location_id: uuid.UUID) -> CartView:
    """The cart re-priced now; lines that cannot be ordered carry `problem`."""
    return await cart.view(session, user_id, location_id)


async def add_to_cart(
    session: AsyncSession,
    user_id: uuid.UUID,
    location_id: uuid.UUID,
    *,
    dish_id: uuid.UUID,
    size_id: uuid.UUID,
    modifier_ids: list[uuid.UUID],
    quantity: int,
) -> None:
    """Raises CartError: incomplete_selection, invalid_selection, bad_quantity."""
    await cart.add(
        session,
        user_id,
        location_id,
        dish_id=dish_id,
        size_id=size_id,
        modifier_ids=modifier_ids,
        quantity=quantity,
    )


async def set_cart_quantity(
    session: AsyncSession,
    user_id: uuid.UUID,
    location_id: uuid.UUID,
    item_id: uuid.UUID,
    quantity: int,
) -> None:
    """0 removes the line."""
    await cart.set_quantity(session, user_id, location_id, item_id, quantity)


async def remove_from_cart(
    session: AsyncSession, user_id: uuid.UUID, location_id: uuid.UUID, item_id: uuid.UUID
) -> None:
    await cart.remove(session, user_id, location_id, item_id)


async def place_order(
    session: AsyncSession,
    user_id: uuid.UUID,
    location_id: uuid.UUID,
    *,
    payment_method: PaymentMethod,
    comment: str,
    now: datetime,
) -> OrderView:
    """Create the order from the cart in one transaction: snapshot, number, log; the cart
    is emptied. Raises OrderError: location_closed, contact_required, empty_cart,
    cart_has_unavailable."""
    return await orders.place(
        session, user_id, location_id, payment_method=payment_method, comment=comment, now=now
    )


async def get_order(session: AsyncSession, order_id: uuid.UUID) -> OrderView | None:
    order = await orders.get(session, order_id)
    return orders.view(order) if order else None


async def list_orders(
    session: AsyncSession, location_id: uuid.UUID, statuses: frozenset[str]
) -> list[OrderView]:
    """Orders of the location in these statuses, oldest first (the staff board)."""
    return await orders.list_orders(session, location_id, statuses)


async def transition(
    session: AsyncSession,
    order_id: uuid.UUID,
    action: str,
    actor: Actor,
    *,
    expected_version: int | None,
    now: datetime,
    ready_at: datetime | None = None,
    note: str | None = None,
    event_extra: dict[str, object] | None = None,
) -> OrderView:
    """The only way to change an order's status (AD-3). See `TRANSITIONS`.

    Writes the log entry and the `ordering.order.<past_tense>` event in the same
    transaction; `event_extra` adds facts the caller knows (e.g. a refund) to the event."""
    return await orders.transition(
        session,
        order_id,
        action,
        actor,
        expected_version=expected_version,
        now=now,
        ready_at=ready_at,
        note=note,
        event_extra=event_extra,
    )


log = structlog.get_logger()

UNPAID_NOTE = "Не оплачен вовремя"


async def overdue_unpaid(session: AsyncSession, now: datetime) -> list[uuid.UUID]:
    return await orders.overdue_unpaid(session, now)


async def cancel_unpaid(session: AsyncSession, order_id: uuid.UUID, now: datetime) -> bool:
    """System cancel of an order nobody paid for in time; False if it moved on meanwhile."""
    try:
        await orders.transition(
            session,
            order_id,
            "cancel",
            SYSTEM,
            expected_version=None,
            now=now,
            note=UNPAID_NOTE,
            event_extra={"unpaid_timeout": True},
        )
    except OrderError as exc:
        if exc.code in ("transition_not_allowed", "order_conflict"):
            return False
        raise
    return True


async def _payment_succeeded(session: AsyncSession, event: Event) -> None:
    order_id = uuid.UUID(event.payload["order_id"])
    order = await orders.get(session, order_id)
    # A repeated event for an order already past `pending_payment` is done (AD-9).
    if order is None or order.status != "pending_payment":
        log.info("ordering.payment_for_settled_order", order_id=str(order_id))
        return
    await orders.transition(
        session, order_id, "payment_succeeded", SYSTEM, expected_version=None, now=datetime.now(UTC)
    )


def subscriptions() -> list[Subscription]:
    """A paid online order goes to the kitchen."""
    return [
        Subscription("payments.payment.succeeded", "ordering.payment_succeeded", _payment_succeeded)
    ]
