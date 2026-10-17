"""The guest's cart (FR-6). Only the choice is stored; every read re-prices it (AD-6)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.catalog import api as catalog
from fenix.modules.ordering.models import Cart, CartItem

MAX_QUANTITY = 99


class CartError(Exception):
    def __init__(self, code: str, status: int = 422, details: dict[str, str] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
        self.details = details or {}


@dataclass(frozen=True, slots=True)
class CartLine:
    id: uuid.UUID
    dish_id: uuid.UUID
    size_id: uuid.UUID
    modifier_ids: list[uuid.UUID]
    quantity: int
    title: str
    size_name: str | None
    modifier_names: list[str]
    photo_key: str | None
    unit_price: int | None
    total_price: int | None
    # None when the line can be ordered; otherwise why not (unavailable, …).
    problem: str | None
    # Before the promotion (FR-5); equal to total_price without one.
    original_total_price: int | None = None
    original_unit_price: int | None = None
    promotion_title: str | None = None
    discount_percent: int = 0


@dataclass(frozen=True, slots=True)
class CartView:
    lines: list[CartLine]
    # Kopecks of the lines that can be ordered now.
    total: int
    count: int
    original_total: int = 0


def _title(quote: catalog.Quote) -> str:
    parts = [quote.dish_name or "Позиция"]
    if quote.size_name:
        parts.append(quote.size_name)
    return " · ".join(parts)


async def _cart(session: AsyncSession, user_id: uuid.UUID, location_id: uuid.UUID) -> Cart:
    # Created on first use; the unique pair makes concurrent first adds safe.
    await session.execute(
        insert(Cart)
        .values(id=uuid.uuid7(), user_id=user_id, location_id=location_id)
        .on_conflict_do_nothing(index_elements=[Cart.user_id, Cart.location_id])
    )
    statement = select(Cart).where(Cart.user_id == user_id, Cart.location_id == location_id)
    return (await session.execute(statement)).scalar_one()


async def view(
    session: AsyncSession,
    user_id: uuid.UUID,
    location_id: uuid.UUID,
    claimed_promotion_id: uuid.UUID | None = None,
) -> CartView:
    cart = (
        await session.execute(
            select(Cart).where(Cart.user_id == user_id, Cart.location_id == location_id)
        )
    ).scalar_one_or_none()
    lines = []
    for item in cart.items if cart else []:
        modifier_ids = [uuid.UUID(m) for m in item.modifier_ids]
        quote = await catalog.quote(
            session,
            location_id=location_id,
            dish_id=item.dish_id,
            size_id=item.size_id,
            modifier_ids=modifier_ids,
            quantity=item.quantity,
            claimed_promotion_id=claimed_promotion_id,
        )
        problem = quote.problem
        if problem is None and quote.price is not None and not quote.price.complete:
            problem = "incomplete_selection"
        priced = quote.price if problem is None else None
        lines.append(
            CartLine(
                id=item.id,
                dish_id=item.dish_id,
                size_id=item.size_id,
                modifier_ids=modifier_ids,
                quantity=item.quantity,
                title=_title(quote) if quote.dish_name else item.title,
                size_name=quote.size_name,
                modifier_names=quote.modifier_names,
                photo_key=quote.photo_key,
                unit_price=priced.unit_price if priced else None,
                total_price=priced.total_price if priced else None,
                problem=problem,
                original_unit_price=priced.original_unit_price if priced else None,
                original_total_price=(
                    priced.original_unit_price * item.quantity if priced else None
                ),
                promotion_title=priced.promotion_title if priced else None,
                discount_percent=priced.discount_percent if priced else 0,
            )
        )
    return CartView(
        lines=lines,
        total=sum(line.total_price or 0 for line in lines),
        count=sum(line.quantity for line in lines if line.problem is None),
        original_total=sum(line.original_total_price or 0 for line in lines),
    )


async def add(
    session: AsyncSession,
    user_id: uuid.UUID,
    location_id: uuid.UUID,
    *,
    dish_id: uuid.UUID,
    size_id: uuid.UUID,
    modifier_ids: list[uuid.UUID],
    quantity: int,
) -> None:
    if not 1 <= quantity <= MAX_QUANTITY:
        raise CartError("bad_quantity")
    quote = await catalog.quote(
        session,
        location_id=location_id,
        dish_id=dish_id,
        size_id=size_id,
        modifier_ids=modifier_ids,
        quantity=quantity,
    )
    if quote.problem is not None:
        raise CartError("invalid_selection", details={"reason": quote.problem})
    if quote.price is None or not quote.price.complete:
        raise CartError("incomplete_selection")

    cart = await _cart(session, user_id, location_id)
    key = sorted(str(m) for m in modifier_ids)
    same = next(
        (
            item
            for item in cart.items
            if item.dish_id == dish_id and item.size_id == size_id and item.modifier_ids == key
        ),
        None,
    )
    if same is not None:
        same.quantity = min(MAX_QUANTITY, same.quantity + quantity)
    else:
        title = _title(quote)
        if quote.modifier_names:
            title += " · " + ", ".join(quote.modifier_names)
        cart.items.append(
            CartItem(
                dish_id=dish_id, size_id=size_id, modifier_ids=key, quantity=quantity, title=title
            )
        )
    await session.flush()


async def _own_item(
    session: AsyncSession, user_id: uuid.UUID, location_id: uuid.UUID, item_id: uuid.UUID
) -> CartItem:
    statement = (
        select(CartItem)
        .join(Cart)
        .where(CartItem.id == item_id, Cart.user_id == user_id, Cart.location_id == location_id)
    )
    item = (await session.execute(statement)).scalar_one_or_none()
    if item is None:
        raise CartError("cart_item_not_found", 404)
    return item


async def set_quantity(
    session: AsyncSession,
    user_id: uuid.UUID,
    location_id: uuid.UUID,
    item_id: uuid.UUID,
    quantity: int,
) -> None:
    item = await _own_item(session, user_id, location_id, item_id)
    if quantity == 0:
        await session.delete(item)
    elif 1 <= quantity <= MAX_QUANTITY:
        item.quantity = quantity
    else:
        raise CartError("bad_quantity")
    await session.flush()


async def remove(
    session: AsyncSession, user_id: uuid.UUID, location_id: uuid.UUID, item_id: uuid.UUID
) -> None:
    await session.delete(await _own_item(session, user_id, location_id, item_id))
    await session.flush()


async def clear(session: AsyncSession, user_id: uuid.UUID, location_id: uuid.UUID) -> None:
    cart = (
        await session.execute(
            select(Cart).where(Cart.user_id == user_id, Cart.location_id == location_id)
        )
    ).scalar_one_or_none()
    if cart is not None:
        cart.items = []
        await session.flush()
