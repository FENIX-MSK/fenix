"""Public API of `ordering`: functions and DTOs, the only import surface for other modules."""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.locations import api as locations
from fenix.modules.ordering import cart, kitchen, orders
from fenix.modules.ordering.cart import CartError, CartLine, CartView
from fenix.modules.ordering.kitchen import KitchenLoad
from fenix.modules.ordering.orders import (
    ACTIVE,
    FINAL,
    SYSTEM,
    TRANSITIONS,
    Actor,
    ActorKind,
    Address,
    Fulfilment,
    LogEntry,
    OrderError,
    OrderLine,
    OrderView,
    PaymentMethod,
    RepeatResult,
)
from fenix.platform.outbox import Event, Subscription

__all__ = [
    "ACTIVE",
    "FINAL",
    "SYSTEM",
    "TRANSITIONS",
    "Actor",
    "Address",
    "CartError",
    "CartLine",
    "CartView",
    "Fulfilment",
    "KitchenLoad",
    "LogEntry",
    "OrderError",
    "OrderLine",
    "OrderView",
    "PaymentMethod",
    "RepeatResult",
    "active_guest_order",
    "add_to_cart",
    "cancel_unpaid",
    "count_by_status",
    "decide_discount",
    "due_scheduled",
    "get_order",
    "guest_orders",
    "is_allowed",
    "kitchen_load",
    "list_orders",
    "orders_between",
    "overdue_unpaid",
    "place_order",
    "preorder_slots",
    "release_scheduled",
    "remove_from_cart",
    "repeat_order",
    "set_cart_quantity",
    "subscriptions",
    "transition",
    "view_cart",
    "view_cart_with_claim",
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
    fulfilment: Fulfilment = "pickup",
    address: Address | None = None,
    change_from: int | None = None,
    scheduled_for: datetime | None = None,
    claimed_promotion_id: uuid.UUID | None = None,
) -> OrderView:
    """Create the order from the cart in one transaction: snapshot, number, log; the cart
    is emptied. Raises OrderError: location_closed, orders_paused, delivery_unavailable,
    address_required, slot_unavailable, contact_required, empty_cart,
    cart_has_unavailable, bad_change, promotion_unavailable, claim_requires_on_site."""
    return await orders.place(
        session,
        user_id,
        location_id,
        payment_method=payment_method,
        comment=comment,
        now=now,
        fulfilment=fulfilment,
        address=address,
        change_from=change_from,
        scheduled_for=scheduled_for,
        claimed_promotion_id=claimed_promotion_id,
    )


async def decide_discount(
    session: AsyncSession,
    order_id: uuid.UUID,
    confirm: bool,
    actor: Actor,
    *,
    expected_version: int,
    now: datetime,
) -> OrderView:
    """FR-23: confirm or remove the claimed «checked» discount."""
    return await orders.decide_discount(
        session, order_id, confirm, actor, expected_version=expected_version, now=now
    )


async def view_cart_with_claim(
    session: AsyncSession, user_id: uuid.UUID, location_id: uuid.UUID, promotion_id: uuid.UUID
) -> CartView:
    """The cart as it would be with the claimed discount: the preliminary total (FR-11)."""
    return await cart.view(session, user_id, location_id, promotion_id)


async def orders_between(
    session: AsyncSession, location_id: uuid.UUID, start: datetime, end: datetime
) -> list[OrderView]:
    """Orders created in [start, end) with their lines and log (reports)."""
    return await orders.orders_between(session, location_id, start, end)


async def count_by_status(session: AsyncSession) -> dict[str, int]:
    """Unfinished orders by status, all locations (metrics)."""
    return await orders.count_by_status(session)


def is_allowed(order: OrderView, action: str, actor: ActorKind) -> bool:
    """Whether the transition table permits it now (AD-3); the CAS still decides races."""
    rule = TRANSITIONS.get((order.status, action))
    return (
        rule is not None
        and actor in rule.actors
        and (rule.fulfilment is None or rule.fulfilment == order.fulfilment)
    )


async def kitchen_load(session: AsyncSession, location_id: uuid.UUID, now: datetime) -> KitchenLoad:
    """«Спокойно / умеренно / загружено» and the waiting time it implies (FR-37)."""
    settings = await locations.get_order_settings(session, location_id, now)
    return await kitchen.kitchen_load(session, location_id, settings)


async def preorder_slots(
    session: AsyncSession, location_id: uuid.UUID, now: datetime
) -> list[datetime]:
    """Today's slots, not earlier than the current waiting time (FR-8)."""
    settings = await locations.get_order_settings(session, location_id, now)
    load = await kitchen.kitchen_load(session, location_id, settings)
    return kitchen.slots(settings, load.wait_minutes, now)


async def due_scheduled(session: AsyncSession, now: datetime) -> list[uuid.UUID]:
    return await orders.due_scheduled(session, now)


async def release_scheduled(session: AsyncSession, order_id: uuid.UUID, now: datetime) -> bool:
    """A preorder goes to the kitchen; False if it moved on meanwhile (cancelled)."""
    try:
        await orders.transition(
            session, order_id, "release", SYSTEM, expected_version=None, now=now
        )
    except OrderError as exc:
        if exc.code in ("transition_not_allowed", "order_conflict"):
            return False
        raise
    return True


async def get_order(session: AsyncSession, order_id: uuid.UUID) -> OrderView | None:
    order = await orders.get(session, order_id)
    return orders.view(order) if order else None


async def guest_orders(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int,
    before: tuple[datetime, uuid.UUID] | None = None,
) -> list[OrderView]:
    """The guest's order history, newest first (FR-17)."""
    return await orders.guest_orders(session, user_id, limit=limit, before=before)


async def active_guest_order(session: AsyncSession, user_id: uuid.UUID) -> OrderView | None:
    """The guest's latest order that is not finished yet (the banner over the menu)."""
    return await orders.active_guest_order(session, user_id)


async def repeat_order(
    session: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID, location_id: uuid.UUID
) -> RepeatResult:
    """Raises OrderError order_not_found (someone else's order too)."""
    return await orders.repeat(session, order_id, user_id, location_id)


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
    # A paid preorder waits for its slot (story 5.5).
    action = "schedule" if order.scheduled_for else "payment_succeeded"
    await orders.transition(
        session, order_id, action, SYSTEM, expected_version=None, now=datetime.now(UTC)
    )


def subscriptions() -> list[Subscription]:
    """A paid online order goes to the kitchen."""
    return [
        Subscription("payments.payment.succeeded", "ordering.payment_succeeded", _payment_succeeded)
    ]
