"""Public API of `ordering`: functions and DTOs, the only import surface for other modules."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.ordering import cart
from fenix.modules.ordering.cart import CartError, CartLine, CartView

__all__ = [
    "CartError",
    "CartLine",
    "CartView",
    "add_to_cart",
    "remove_from_cart",
    "set_cart_quantity",
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
