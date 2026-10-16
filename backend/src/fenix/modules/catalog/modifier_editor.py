"""Staff editing of modifier groups and where they apply (FR-26)."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fenix.modules.catalog.editor import CatalogEditError, NotFoundError, _clean
from fenix.modules.catalog.models import (
    Category,
    CategoryModifierGroup,
    Dish,
    DishModifierGroup,
    Modifier,
    ModifierGroup,
)


@dataclass(frozen=True, slots=True)
class OptionInput:
    id: uuid.UUID | None
    name: str
    price_delta: int


@dataclass(frozen=True, slots=True)
class GroupInput:
    name: str
    min_choice: int
    max_choice: int
    options: Sequence[OptionInput]


@dataclass(frozen=True, slots=True)
class GroupLinks:
    dish_ids: list[uuid.UUID]
    category_ids: list[uuid.UUID]


def _check(data: GroupInput) -> None:
    if not data.options:
        raise CatalogEditError("group_needs_option")
    names = [option.name.strip() for option in data.options]
    if not all(names):
        raise CatalogEditError("name_required")
    if len(set(names)) != len(names):
        raise CatalogEditError("duplicate_option_name")
    if not 0 <= data.min_choice <= data.max_choice or not 1 <= data.max_choice <= len(names):
        raise CatalogEditError("choice_bounds")
    if any(option.price_delta < 0 for option in data.options):
        raise CatalogEditError("bad_price")


async def list_groups(session: AsyncSession) -> list[tuple[ModifierGroup, GroupLinks]]:
    groups = (
        (
            await session.execute(
                select(ModifierGroup)
                .order_by(ModifierGroup.created_at, ModifierGroup.id)
                .options(selectinload(ModifierGroup.modifiers))
            )
        )
        .scalars()
        .all()
    )
    dish_links = (await session.execute(select(DishModifierGroup))).scalars().all()
    category_links = (await session.execute(select(CategoryModifierGroup))).scalars().all()
    return [
        (
            group,
            GroupLinks(
                dish_ids=[link.dish_id for link in dish_links if link.group_id == group.id],
                category_ids=[
                    link.category_id for link in category_links if link.group_id == group.id
                ],
            ),
        )
        for group in groups
    ]


async def _group(session: AsyncSession, group_id: uuid.UUID) -> ModifierGroup:
    statement = (
        select(ModifierGroup)
        .where(ModifierGroup.id == group_id)
        .options(selectinload(ModifierGroup.modifiers))
    )
    group = (await session.execute(statement)).scalar_one_or_none()
    if group is None:
        raise NotFoundError("modifier_group")
    return group


def _apply(group: ModifierGroup, data: GroupInput) -> None:
    group.name = _clean(data.name)
    group.min_choice = data.min_choice
    group.max_choice = data.max_choice
    existing = {modifier.id: modifier for modifier in group.modifiers}
    kept = []
    for position, option in enumerate(data.options):
        if option.id is None:
            row = Modifier()
        elif option.id in existing:
            row = existing[option.id]
        else:
            raise CatalogEditError("foreign_modifier")
        row.name = option.name.strip()
        row.price_delta = option.price_delta
        row.position = position
        kept.append(row)
    group.modifiers = kept


async def create_group(session: AsyncSession, data: GroupInput) -> ModifierGroup:
    _check(data)
    group = ModifierGroup(modifiers=[])
    _apply(group, data)
    session.add(group)
    await session.flush()
    return group


async def update_group(session: AsyncSession, group_id: uuid.UUID, data: GroupInput) -> None:
    _check(data)
    _apply(await _group(session, group_id), data)
    await session.flush()


async def delete_group(session: AsyncSession, group_id: uuid.UUID) -> None:
    await session.delete(await _group(session, group_id))
    await session.flush()


async def set_links(session: AsyncSession, group_id: uuid.UUID, links: GroupLinks) -> None:
    await _group(session, group_id)
    dish_ids, category_ids = set(links.dish_ids), set(links.category_ids)
    found_dishes = set(
        (await session.execute(select(Dish.id).where(Dish.id.in_(dish_ids)))).scalars()
    )
    found_categories = set(
        (await session.execute(select(Category.id).where(Category.id.in_(category_ids)))).scalars()
    )
    if found_dishes != dish_ids or found_categories != category_ids:
        raise CatalogEditError("unknown_link")

    await session.execute(
        delete(DishModifierGroup).where(
            DishModifierGroup.group_id == group_id, DishModifierGroup.dish_id.not_in(dish_ids)
        )
    )
    await session.execute(
        delete(CategoryModifierGroup).where(
            CategoryModifierGroup.group_id == group_id,
            CategoryModifierGroup.category_id.not_in(category_ids),
        )
    )
    linked_dishes = set(
        (
            await session.execute(
                select(DishModifierGroup.dish_id).where(DishModifierGroup.group_id == group_id)
            )
        ).scalars()
    )
    linked_categories = set(
        (
            await session.execute(
                select(CategoryModifierGroup.category_id).where(
                    CategoryModifierGroup.group_id == group_id
                )
            )
        ).scalars()
    )
    # A new link goes after the groups already shown for that dish or category.
    for dish_id in dish_ids - linked_dishes:
        session.add(DishModifierGroup(dish_id=dish_id, group_id=group_id, position=100))
    for category_id in category_ids - linked_categories:
        session.add(CategoryModifierGroup(category_id=category_id, group_id=group_id, position=100))
    await session.flush()
