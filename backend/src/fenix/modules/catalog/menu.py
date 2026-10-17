"""The guest menu of a location: visible categories and dishes with prices and availability."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fenix.modules.catalog import promotions
from fenix.modules.catalog.models import Category, Dish, StopListEntry


@dataclass(frozen=True, slots=True)
class MenuDish:
    id: uuid.UUID
    name: str
    description: str
    portion: str | None
    # Kopecks: the lowest price among available sizes (among all when none is left).
    price_from: int
    has_sizes: bool
    sold_out: bool
    photo_key: str | None
    # Before the automatic promotion (FR-5): shown struck through when it differs.
    original_price_from: int = 0
    discount_percent: int = 0


@dataclass(frozen=True, slots=True)
class MenuCategory:
    id: uuid.UUID
    name: str
    description: str
    dishes: list[MenuDish]


async def stopped_size_ids(session: AsyncSession, location_id: uuid.UUID) -> set[uuid.UUID]:
    rows = await session.execute(
        select(StopListEntry.dish_size_id).where(
            StopListEntry.location_id == location_id, StopListEntry.dish_size_id.is_not(None)
        )
    )
    return {size_id for size_id in rows.scalars() if size_id is not None}


def _menu_dish(dish: Dish, stopped: set[uuid.UUID], percent: int) -> MenuDish:
    available = [size for size in dish.sizes if size.id not in stopped]
    priced = available or dish.sizes
    lowest = min(size.price for size in priced)
    return MenuDish(
        id=dish.id,
        name=dish.name,
        description=dish.description,
        portion=dish.portion or (dish.sizes[0].portion if dish.sizes else None),
        price_from=promotions.discounted(lowest, percent) if percent else lowest,
        original_price_from=lowest,
        discount_percent=percent,
        has_sizes=len(dish.sizes) > 1,
        sold_out=not available,
        photo_key=dish.photo_key,
    )


async def get_menu(session: AsyncSession, location_id: uuid.UUID) -> list[MenuCategory]:
    # Three queries regardless of menu size: categories, their dishes, the dishes' sizes,
    # plus one for the stop list.
    statement = (
        select(Category)
        .where(Category.is_hidden.is_(False))
        .order_by(Category.position)
        .options(selectinload(Category.dishes).selectinload(Dish.sizes))
    )
    categories = (await session.execute(statement)).scalars().all()
    stopped = await stopped_size_ids(session, location_id)
    today = await promotions.local_today(session, location_id)
    active = await promotions.active(session, location_id, today)

    def percent(category_id: uuid.UUID) -> int:
        best = promotions.best_for(active, category_id, None)
        return best.percent if best else 0

    return [
        MenuCategory(
            id=category.id,
            name=category.name,
            description=category.description,
            dishes=[
                _menu_dish(dish, stopped, percent(category.id))
                for dish in category.dishes
                if not dish.is_hidden and dish.sizes
            ],
        )
        for category in categories
    ]
