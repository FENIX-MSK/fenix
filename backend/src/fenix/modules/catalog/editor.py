"""Staff editing of categories, dishes and sizes (FR-26)."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fenix.modules.catalog.models import Category, Dish, DishSize


class CatalogEditError(Exception):
    """A rejected edit; `code` is a stable snake_case error code."""

    def __init__(self, code: str, status: int = 422) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


class NotFoundError(CatalogEditError):
    def __init__(self, what: str) -> None:
        super().__init__(f"{what}_not_found", 404)


@dataclass(frozen=True, slots=True)
class SizeInput:
    id: uuid.UUID | None
    name: str
    price: int
    portion: str | None


@dataclass(frozen=True, slots=True)
class DishInput:
    category_id: uuid.UUID
    name: str
    description: str
    portion: str | None
    is_hidden: bool
    sizes: Sequence[SizeInput]


async def staff_catalog(session: AsyncSession) -> list[Category]:
    """Everything, hidden included, in menu order, with group links (story 2.4)."""
    statement = (
        select(Category)
        .order_by(Category.position)
        .options(
            selectinload(Category.dishes).selectinload(Dish.sizes),
            selectinload(Category.dishes).selectinload(Dish.modifier_groups),
            selectinload(Category.modifier_groups),
        )
    )
    return list((await session.execute(statement)).scalars())


async def _category(session: AsyncSession, category_id: uuid.UUID) -> Category:
    category = await session.get(Category, category_id)
    if category is None:
        raise NotFoundError("category")
    return category


async def _dish(session: AsyncSession, dish_id: uuid.UUID) -> Dish:
    statement = select(Dish).where(Dish.id == dish_id).options(selectinload(Dish.sizes))
    dish = (await session.execute(statement)).scalar_one_or_none()
    if dish is None:
        raise NotFoundError("dish")
    return dish


def _clean(name: str) -> str:
    name = name.strip()
    if not name:
        raise CatalogEditError("name_required")
    return name


async def create_category(
    session: AsyncSession, name: str, description: str, is_hidden: bool
) -> Category:
    last = (await session.execute(select(func.max(Category.position)))).scalar_one()
    category = Category(
        name=_clean(name),
        description=description.strip(),
        is_hidden=is_hidden,
        position=0 if last is None else last + 1,
    )
    session.add(category)
    await session.flush()
    return category


async def update_category(
    session: AsyncSession, category_id: uuid.UUID, name: str, description: str, is_hidden: bool
) -> Category:
    category = await _category(session, category_id)
    category.name = _clean(name)
    category.description = description.strip()
    category.is_hidden = is_hidden
    await session.flush()
    return category


async def delete_category(session: AsyncSession, category_id: uuid.UUID) -> None:
    category = await _category(session, category_id)
    has_dishes = await session.execute(select(exists().where(Dish.category_id == category.id)))
    if has_dishes.scalar_one():
        raise CatalogEditError("category_not_empty", 409)
    await session.delete(category)
    await session.flush()


def _check_sizes(sizes: Sequence[SizeInput]) -> None:
    if not sizes:
        raise CatalogEditError("dish_needs_size")
    names = [size.name.strip() for size in sizes]
    if len(sizes) > 1 and not all(names):
        raise CatalogEditError("size_name_required")
    if len(set(names)) != len(names):
        raise CatalogEditError("duplicate_size_name")
    if any(size.price < 0 for size in sizes):
        raise CatalogEditError("bad_price")


def _apply_sizes(dish: Dish, sizes: Sequence[SizeInput]) -> None:
    existing = {size.id: size for size in dish.sizes}
    kept = []
    for position, size in enumerate(sizes):
        if size.id is None:
            row = DishSize()
        elif size.id in existing:
            row = existing[size.id]
        else:
            raise CatalogEditError("foreign_size")
        row.name = size.name.strip()
        row.price = size.price
        row.portion = (size.portion or "").strip() or None
        row.position = position
        kept.append(row)
    # Sizes left out are deleted (delete-orphan), with their stop-list entries (FK cascade).
    dish.sizes = kept


async def create_dish(session: AsyncSession, data: DishInput) -> Dish:
    _check_sizes(data.sizes)
    await _category(session, data.category_id)
    last = (
        await session.execute(
            select(func.max(Dish.position)).where(Dish.category_id == data.category_id)
        )
    ).scalar_one()
    dish = Dish(
        category_id=data.category_id,
        name=_clean(data.name),
        description=data.description.strip(),
        portion=(data.portion or "").strip() or None,
        is_hidden=data.is_hidden,
        position=0 if last is None else last + 1,
        sizes=[],
    )
    _apply_sizes(dish, data.sizes)
    session.add(dish)
    await session.flush()
    return dish


async def update_dish(session: AsyncSession, dish_id: uuid.UUID, data: DishInput) -> Dish:
    _check_sizes(data.sizes)
    dish = await _dish(session, dish_id)
    if data.category_id != dish.category_id:
        await _category(session, data.category_id)
        last = (
            await session.execute(
                select(func.max(Dish.position)).where(Dish.category_id == data.category_id)
            )
        ).scalar_one()
        dish.category_id = data.category_id
        dish.position = 0 if last is None else last + 1
    dish.name = _clean(data.name)
    dish.description = data.description.strip()
    dish.portion = (data.portion or "").strip() or None
    dish.is_hidden = data.is_hidden
    _apply_sizes(dish, data.sizes)
    await session.flush()
    return dish


async def delete_dish(session: AsyncSession, dish_id: uuid.UUID) -> None:
    await session.delete(await _dish(session, dish_id))
    await session.flush()


async def reorder_categories(session: AsyncSession, ids: Sequence[uuid.UUID]) -> None:
    categories = list((await session.execute(select(Category))).scalars())
    _reorder(categories, ids)
    await session.flush()


async def reorder_dishes(
    session: AsyncSession, category_id: uuid.UUID, ids: Sequence[uuid.UUID]
) -> None:
    await _category(session, category_id)
    dishes = list(
        (await session.execute(select(Dish).where(Dish.category_id == category_id))).scalars()
    )
    _reorder(dishes, ids)
    await session.flush()


def _reorder(rows: Sequence[Category] | Sequence[Dish], ids: Sequence[uuid.UUID]) -> None:
    by_id = {row.id: row for row in rows}
    if len(ids) != len(by_id) or set(ids) != set(by_id):
        raise CatalogEditError("bad_order")
    for position, row_id in enumerate(ids):
        by_id[row_id].position = position
