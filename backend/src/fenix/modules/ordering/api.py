"""Public API of `ordering`: functions and DTOs, the only import surface for other modules."""

import uuid
from datetime import datetime

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
    "get_order",
    "place_order",
    "remove_from_cart",
    "set_cart_quantity",
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
) -> OrderView:
    """The only way to change an order's status (AD-3). See `TRANSITIONS`."""
    return await orders.transition(
        session,
        order_id,
        action,
        actor,
        expected_version=expected_version,
        now=now,
        ready_at=ready_at,
        note=note,
    )
