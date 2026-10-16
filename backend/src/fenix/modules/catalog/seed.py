from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.catalog.menu_data import MENU, CategoryData, GroupData
from fenix.modules.catalog.models import (
    Category,
    CategoryModifierGroup,
    Dish,
    DishModifierGroup,
    DishSize,
    Modifier,
    ModifierGroup,
)

KOPECKS = 100


def _group(data: GroupData) -> ModifierGroup:
    return ModifierGroup(
        name=data.name,
        min_choice=data.min_choice,
        max_choice=data.max_choice,
        modifiers=[
            Modifier(name=name, price_delta=price * KOPECKS, position=position)
            for position, (name, price) in enumerate(data.options)
        ],
    )


def _category(data: CategoryData, position: int, groups: dict[str, ModifierGroup]) -> Category:
    def shared(group: GroupData) -> ModifierGroup:
        # One row per group, even when several dishes use it (the burger patty).
        if group.name not in groups:
            groups[group.name] = _group(group)
        return groups[group.name]

    category = Category(name=data.name, description=data.description, position=position)
    category.modifier_groups = [
        CategoryModifierGroup(group=shared(group), position=index)
        for index, group in enumerate(data.groups)
    ]
    for index, dish_data in enumerate(data.dishes):
        sizes = dish_data.sizes or ()
        if not sizes:
            if dish_data.price is None:
                raise ValueError(f"{dish_data.name}: neither price nor sizes")
            size_rows = [DishSize(name="", price=dish_data.price * KOPECKS, position=0)]
        else:
            size_rows = [
                DishSize(name=s.name, price=s.price * KOPECKS, portion=s.portion, position=i)
                for i, s in enumerate(sizes)
            ]
        dish = Dish(
            name=dish_data.name,
            description=dish_data.description,
            portion=dish_data.portion,
            position=index,
            sizes=size_rows,
            modifier_groups=[
                DishModifierGroup(group=shared(group), position=i)
                for i, group in enumerate(dish_data.groups)
            ],
        )
        category.dishes.append(dish)
    return category


async def seed_menu(session: AsyncSession) -> bool:
    """Load the printed menu once. Skipped entirely when the catalog has any category,
    so a re-run neither duplicates rows nor brings back what staff removed."""
    if (await session.execute(select(Category.id).limit(1))).first() is not None:
        return False
    groups: dict[str, ModifierGroup] = {}
    session.add_all(_category(data, position, groups) for position, data in enumerate(MENU))
    await session.flush()
    return True
