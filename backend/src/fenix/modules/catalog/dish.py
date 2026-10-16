"""One dish with everything a guest can choose, and its availability at a location."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fenix.modules.catalog.models import (
    Category,
    CategoryModifierGroup,
    Dish,
    DishModifierGroup,
    ModifierGroup,
    StopListEntry,
)


@dataclass(frozen=True, slots=True)
class SizeOption:
    id: uuid.UUID
    name: str
    price: int
    portion: str | None
    available: bool


@dataclass(frozen=True, slots=True)
class ModifierOption:
    id: uuid.UUID
    name: str
    price_delta: int
    available: bool


@dataclass(frozen=True, slots=True)
class GroupOption:
    id: uuid.UUID
    name: str
    min_choice: int
    max_choice: int
    modifiers: list[ModifierOption]


@dataclass(frozen=True, slots=True)
class DishDetail:
    id: uuid.UUID
    name: str
    description: str
    portion: str | None
    photo_key: str | None
    sizes: list[SizeOption]
    groups: list[GroupOption]


@dataclass(frozen=True, slots=True)
class StopList:
    size_ids: frozenset[uuid.UUID]
    modifier_ids: frozenset[uuid.UUID]


async def load_stop_list(session: AsyncSession, location_id: uuid.UUID) -> StopList:
    rows = await session.execute(
        select(StopListEntry.dish_size_id, StopListEntry.modifier_id).where(
            StopListEntry.location_id == location_id
        )
    )
    sizes, modifiers = set(), set()
    for size_id, modifier_id in rows:
        if size_id is not None:
            sizes.add(size_id)
        if modifier_id is not None:
            modifiers.add(modifier_id)
    return StopList(frozenset(sizes), frozenset(modifiers))


async def load_visible_dish(session: AsyncSession, dish_id: uuid.UUID) -> Dish | None:
    """The dish with sizes and all its groups, or None when it or its category is hidden."""
    with_modifiers = selectinload(ModifierGroup.modifiers)
    statement = (
        select(Dish)
        .join(Category)
        .where(Dish.id == dish_id, Dish.is_hidden.is_(False), Category.is_hidden.is_(False))
        .options(
            selectinload(Dish.sizes),
            selectinload(Dish.modifier_groups)
            .selectinload(DishModifierGroup.group)
            .options(with_modifiers),
            selectinload(Dish.category)
            .selectinload(Category.modifier_groups)
            .selectinload(CategoryModifierGroup.group)
            .options(with_modifiers),
        )
    )
    return (await session.execute(statement)).scalar_one_or_none()


def dish_groups(dish: Dish) -> list[ModifierGroup]:
    """The dish's own groups first, then the category's; each group once."""
    seen: set[uuid.UUID] = set()
    groups = []
    links: list[DishModifierGroup | CategoryModifierGroup] = [
        *dish.modifier_groups,
        *dish.category.modifier_groups,
    ]
    for link in links:
        if link.group_id not in seen:
            seen.add(link.group_id)
            groups.append(link.group)
    return groups


async def get_dish(
    session: AsyncSession, location_id: uuid.UUID, dish_id: uuid.UUID
) -> DishDetail | None:
    dish = await load_visible_dish(session, dish_id)
    if dish is None:
        return None
    stopped = await load_stop_list(session, location_id)
    return DishDetail(
        id=dish.id,
        name=dish.name,
        description=dish.description,
        portion=dish.portion,
        photo_key=dish.photo_key,
        sizes=[
            SizeOption(s.id, s.name, s.price, s.portion, s.id not in stopped.size_ids)
            for s in dish.sizes
        ],
        groups=[
            GroupOption(
                id=group.id,
                name=group.name,
                min_choice=group.min_choice,
                max_choice=group.max_choice,
                modifiers=[
                    ModifierOption(m.id, m.name, m.price_delta, m.id not in stopped.modifier_ids)
                    for m in group.modifiers
                ],
            )
            for group in dish_groups(dish)
        ],
    )
