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


@router.get("/menu")
async def get_menu(session: SessionDep) -> MenuOut:
    location_id = await locations.get_default_location_id(session)
    if location_id is None:
        raise ApiError(404, "location_not_found", "No location is configured")
    categories = await catalog.get_menu(session, location_id)
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
