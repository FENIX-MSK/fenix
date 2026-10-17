"""The only place a price is computed (AD-6). Promotions join here in epic 6."""

import uuid
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fenix.modules.catalog.dish import dish_groups, load_stop_list, load_visible_dish
from fenix.modules.catalog.models import Dish, Modifier


class InvalidSelectionError(Exception):
    """The selection cannot be ordered; `reason` is a stable snake_case code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class MissingGroup:
    id: uuid.UUID
    name: str


@dataclass(frozen=True, slots=True)
class Price:
    # Kopecks for one item and for the whole quantity.
    unit_price: int
    total_price: int
    # False while a required group has fewer choices than its minimum.
    complete: bool
    missing_groups: list[MissingGroup]


async def price(
    session: AsyncSession,
    *,
    location_id: uuid.UUID,
    dish_id: uuid.UUID,
    size_id: uuid.UUID,
    modifier_ids: list[uuid.UUID],
    quantity: int,
) -> Price:
    if quantity < 1:
        raise InvalidSelectionError("bad_quantity")
    dish = await load_visible_dish(session, dish_id)
    if dish is None:
        raise InvalidSelectionError("dish_unavailable")
    stopped = await load_stop_list(session, location_id)

    size = next((s for s in dish.sizes if s.id == size_id), None)
    if size is None:
        raise InvalidSelectionError("foreign_size")
    if size.id in stopped.size_ids:
        raise InvalidSelectionError("unavailable")

    if len(set(modifier_ids)) != len(modifier_ids):
        raise InvalidSelectionError("duplicate_modifier")
    groups = dish_groups(dish)
    group_of = {m.id: g for g in groups for m in g.modifiers}
    modifiers = {m.id: m for g in groups for m in g.modifiers}
    if any(modifier_id not in modifiers for modifier_id in modifier_ids):
        raise InvalidSelectionError("foreign_modifier")
    if any(modifier_id in stopped.modifier_ids for modifier_id in modifier_ids):
        raise InvalidSelectionError("unavailable")

    chosen_per_group = Counter(group_of[modifier_id].id for modifier_id in modifier_ids)
    if any(chosen_per_group[g.id] > g.max_choice for g in groups):
        raise InvalidSelectionError("too_many")
    missing = [MissingGroup(g.id, g.name) for g in groups if chosen_per_group[g.id] < g.min_choice]

    unit_price = size.price + sum(
        modifiers[modifier_id].price_delta for modifier_id in modifier_ids
    )
    return Price(
        unit_price=unit_price,
        total_price=unit_price * quantity,
        complete=not missing,
        missing_groups=missing,
    )


@dataclass(frozen=True, slots=True)
class Quote:
    """A price that never raises: what a cart line shows, available or not."""

    price: Price | None
    # InvalidSelectionError.reason when the selection cannot be ordered now.
    problem: str | None
    dish_name: str | None
    size_name: str | None
    modifier_names: list[str]
    photo_key: str | None


async def quote(
    session: AsyncSession,
    *,
    location_id: uuid.UUID,
    dish_id: uuid.UUID,
    size_id: uuid.UUID,
    modifier_ids: list[uuid.UUID],
    quantity: int,
) -> Quote:
    dish = await session.get(Dish, dish_id, options=[selectinload(Dish.sizes)])
    size = next((s for s in dish.sizes if s.id == size_id), None) if dish else None
    names = {
        m.id: m.name
        for m in (
            await session.execute(select(Modifier).where(Modifier.id.in_(modifier_ids)))
        ).scalars()
    }
    try:
        result: Price | None = await price(
            session,
            location_id=location_id,
            dish_id=dish_id,
            size_id=size_id,
            modifier_ids=modifier_ids,
            quantity=quantity,
        )
        problem = None
    except InvalidSelectionError as exc:
        result, problem = None, exc.reason
    return Quote(
        price=result,
        problem=problem,
        dish_name=dish.name if dish else None,
        size_name=size.name if size else None,
        modifier_names=[names[m] for m in modifier_ids if m in names],
        photo_key=dish.photo_key if dish else None,
    )
