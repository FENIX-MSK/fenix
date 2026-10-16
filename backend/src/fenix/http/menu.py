import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from fenix.http.deps import SessionDep
from fenix.modules.catalog import api as catalog
from fenix.modules.locations import api as locations
from fenix.platform.errors import ApiError

router = APIRouter(tags=["menu"])


class MenuDishOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    portion: str | None = Field(description="Weight or volume as printed, e.g. «190 г»")
    price_from: int = Field(description="Kopecks; the lowest price of an available size")
    has_sizes: bool = Field(description="Several sizes: show the price as «от N ₽»")
    sold_out: bool
    photo_url: str | None


class MenuCategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    dishes: list[MenuDishOut]


class MenuOut(BaseModel):
    categories: list[MenuCategoryOut]


class SizeOut(BaseModel):
    id: uuid.UUID
    name: str = Field(description="Empty for a dish with a single price")
    price: int = Field(description="Kopecks")
    portion: str | None
    available: bool


class ModifierOut(BaseModel):
    id: uuid.UUID
    name: str
    price_delta: int = Field(description="Kopecks added to the size price")
    available: bool


class ModifierGroupOut(BaseModel):
    id: uuid.UUID
    name: str
    min_choice: int
    max_choice: int
    modifiers: list[ModifierOut]


class DishOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    portion: str | None
    photo_url: str | None
    sizes: list[SizeOut]
    groups: list[ModifierGroupOut]


class PriceIn(BaseModel):
    dish_id: uuid.UUID
    size_id: uuid.UUID
    modifier_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    quantity: int = Field(ge=1, le=99)


class MissingGroupOut(BaseModel):
    id: uuid.UUID
    name: str


class PriceOut(BaseModel):
    unit_price: int = Field(description="Kopecks for one item")
    total_price: int = Field(description="Kopecks for the whole quantity")
    complete: bool = Field(description="False while a required group is not chosen")
    missing_groups: list[MissingGroupOut]


async def _location_id(session: SessionDep) -> uuid.UUID:
    location_id = await locations.get_default_location_id(session)
    if location_id is None:
        raise ApiError(404, "location_not_found", "No location is configured")
    return location_id


@router.get("/menu")
async def get_menu(session: SessionDep) -> MenuOut:
    categories = await catalog.get_menu(session, await _location_id(session))
    return MenuOut(
        categories=[
            MenuCategoryOut(
                id=category.id,
                name=category.name,
                description=category.description,
                dishes=[
                    MenuDishOut(
                        id=dish.id,
                        name=dish.name,
                        description=dish.description,
                        portion=dish.portion,
                        price_from=dish.price_from,
                        has_sizes=dish.has_sizes,
                        sold_out=dish.sold_out,
                        # Photos arrive with the media storage (story 2.5).
                        photo_url=None,
                    )
                    for dish in category.dishes
                ],
            )
            for category in categories
        ]
    )


@router.get("/menu/dishes/{dish_id}")
async def get_dish(dish_id: uuid.UUID, session: SessionDep) -> DishOut:
    dish = await catalog.get_dish(session, await _location_id(session), dish_id)
    if dish is None:
        raise ApiError(404, "dish_not_found", "The dish is not on the menu")
    return DishOut(
        id=dish.id,
        name=dish.name,
        description=dish.description,
        portion=dish.portion,
        photo_url=None,
        sizes=[
            SizeOut(id=s.id, name=s.name, price=s.price, portion=s.portion, available=s.available)
            for s in dish.sizes
        ],
        groups=[
            ModifierGroupOut(
                id=g.id,
                name=g.name,
                min_choice=g.min_choice,
                max_choice=g.max_choice,
                modifiers=[
                    ModifierOut(
                        id=m.id, name=m.name, price_delta=m.price_delta, available=m.available
                    )
                    for m in g.modifiers
                ],
            )
            for g in dish.groups
        ],
    )


@router.post("/menu/price")
async def price(selection: PriceIn, session: SessionDep) -> PriceOut:
    try:
        result = await catalog.price(
            session,
            location_id=await _location_id(session),
            dish_id=selection.dish_id,
            size_id=selection.size_id,
            modifier_ids=selection.modifier_ids,
            quantity=selection.quantity,
        )
    except catalog.InvalidSelectionError as exc:
        raise ApiError(
            422, "invalid_selection", "This selection cannot be ordered", {"reason": exc.reason}
        ) from exc
    return PriceOut(
        unit_price=result.unit_price,
        total_price=result.total_price,
        complete=result.complete,
        missing_groups=[MissingGroupOut(id=g.id, name=g.name) for g in result.missing_groups],
    )
