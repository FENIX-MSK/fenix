"""The only place a price is computed (AD-6). Promotions join here in epic 6."""

import uuid
from collections import Counter
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.catalog.dish import dish_groups, load_stop_list, load_visible_dish


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
