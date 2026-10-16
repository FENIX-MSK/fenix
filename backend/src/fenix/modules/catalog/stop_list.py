"""Staff stop list: what ran out at a location (FR-28, AD-10)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fenix.modules.catalog.dish import load_stop_list
from fenix.modules.catalog.editor import CatalogEditError, NotFoundError
from fenix.modules.catalog.models import (
    Category,
    Dish,
    DishSize,
    Modifier,
    ModifierGroup,
    StopListEntry,
)


@dataclass(frozen=True, slots=True)
class StopItem:
    id: uuid.UUID
    name: str
    stopped: bool


@dataclass(frozen=True, slots=True)
class StopDish:
    id: uuid.UUID
    name: str
    category: str
    is_hidden: bool
    sizes: list[StopItem]


@dataclass(frozen=True, slots=True)
class StopGroup:
    id: uuid.UUID
    name: str
    modifiers: list[StopItem]


async def view(
    session: AsyncSession, location_id: uuid.UUID
) -> tuple[list[StopDish], list[StopGroup]]:
    stopped = await load_stop_list(session, location_id)
    categories = (
        await session.execute(
            select(Category)
            .order_by(Category.position)
            .options(selectinload(Category.dishes).selectinload(Dish.sizes))
        )
    ).scalars()
    dishes = [
        StopDish(
            id=dish.id,
            name=dish.name,
            category=category.name,
            is_hidden=dish.is_hidden or category.is_hidden,
            sizes=[StopItem(s.id, s.name, s.id in stopped.size_ids) for s in dish.sizes],
        )
        for category in categories
        for dish in category.dishes
    ]
    groups = (
        await session.execute(
            select(ModifierGroup)
            .order_by(ModifierGroup.created_at, ModifierGroup.id)
            .options(selectinload(ModifierGroup.modifiers))
        )
    ).scalars()
    return dishes, [
        StopGroup(
            id=group.id,
            name=group.name,
            modifiers=[
                StopItem(m.id, m.name, m.id in stopped.modifier_ids) for m in group.modifiers
            ],
        )
        for group in groups
    ]


async def set_stopped(
    session: AsyncSession,
    location_id: uuid.UUID,
    *,
    size_id: uuid.UUID | None,
    modifier_id: uuid.UUID | None,
    stopped: bool,
) -> None:
    if (size_id is None) == (modifier_id is None):
        raise CatalogEditError("bad_target")
    if size_id is not None and await session.get(DishSize, size_id) is None:
        raise NotFoundError("size")
    if modifier_id is not None and await session.get(Modifier, modifier_id) is None:
        raise NotFoundError("modifier")

    column = StopListEntry.dish_size_id if size_id is not None else StopListEntry.modifier_id
    target = size_id if size_id is not None else modifier_id
    if stopped:
        # The partial unique index makes a repeated "stop" a no-op.
        await session.execute(
            insert(StopListEntry)
            .values(
                id=uuid.uuid7(),
                location_id=location_id,
                dish_size_id=size_id,
                modifier_id=modifier_id,
            )
            .on_conflict_do_nothing()
        )
    else:
        await session.execute(
            delete(StopListEntry).where(StopListEntry.location_id == location_id, column == target)
        )
