"""Staff menu editor (FR-26). Mounted under /api/v1/staff, so every route needs staff."""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from fenix.http.deps import SessionDep
from fenix.modules.catalog import api as catalog
from fenix.platform.errors import ApiError

router = APIRouter(tags=["staff-catalog"])


class StaffSizeOut(BaseModel):
    id: uuid.UUID
    name: str
    price: int = Field(description="Kopecks")
    portion: str | None


class StaffDishOut(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    description: str
    portion: str | None
    is_hidden: bool
    photo_url: str | None
    sizes: list[StaffSizeOut]
    group_ids: list[uuid.UUID]


class StaffCategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    is_hidden: bool
    dishes: list[StaffDishOut]
    group_ids: list[uuid.UUID]


class StaffCatalogOut(BaseModel):
    categories: list[StaffCategoryOut]


class CategoryIn(BaseModel):
    name: str = Field(max_length=128)
    description: str = Field(default="", max_length=500)
    is_hidden: bool = False


class SizeIn(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field(default="", max_length=64)
    price: int = Field(ge=0, le=10_000_000, description="Kopecks")
    portion: str | None = Field(default=None, max_length=32)


class DishIn(BaseModel):
    category_id: uuid.UUID
    name: str = Field(max_length=256)
    description: str = Field(default="", max_length=2000)
    portion: str | None = Field(default=None, max_length=32)
    is_hidden: bool = False
    sizes: list[SizeIn] = Field(max_length=20)


class CreatedOut(BaseModel):
    id: uuid.UUID


class OrderIn(BaseModel):
    ids: list[uuid.UUID]


class DishOrderIn(OrderIn):
    category_id: uuid.UUID


def photo_url(key: str | None) -> str | None:
    return f"/media/{key}" if key else None


def _rejected(exc: catalog.CatalogEditError) -> ApiError:
    return ApiError(exc.status, exc.code, "The menu change was rejected")


def _dish_input(body: DishIn) -> catalog.DishInput:
    return catalog.DishInput(
        category_id=body.category_id,
        name=body.name,
        description=body.description,
        portion=body.portion,
        is_hidden=body.is_hidden,
        sizes=[catalog.SizeInput(s.id, s.name, s.price, s.portion) for s in body.sizes],
    )


@router.get("/catalog")
async def get_catalog(session: SessionDep) -> StaffCatalogOut:
    return StaffCatalogOut(
        categories=[
            StaffCategoryOut(
                id=c.id,
                name=c.name,
                description=c.description,
                is_hidden=c.is_hidden,
                group_ids=c.group_ids,
                dishes=[
                    StaffDishOut(
                        id=d.id,
                        category_id=d.category_id,
                        name=d.name,
                        description=d.description,
                        portion=d.portion,
                        is_hidden=d.is_hidden,
                        photo_url=photo_url(d.photo_key),
                        group_ids=d.group_ids,
                        sizes=[
                            StaffSizeOut(id=s.id, name=s.name, price=s.price, portion=s.portion)
                            for s in d.sizes
                        ],
                    )
                    for d in c.dishes
                ],
            )
            for c in await catalog.staff_catalog(session)
        ]
    )


@router.post("/categories")
async def create_category(body: CategoryIn, session: SessionDep) -> CreatedOut:
    try:
        category_id = await catalog.create_category(
            session, name=body.name, description=body.description, is_hidden=body.is_hidden
        )
    except catalog.CatalogEditError as exc:
        raise _rejected(exc) from exc
    return CreatedOut(id=category_id)


@router.put("/categories/{category_id}")
async def update_category(category_id: uuid.UUID, body: CategoryIn, session: SessionDep) -> None:
    try:
        await catalog.update_category(
            session,
            category_id,
            name=body.name,
            description=body.description,
            is_hidden=body.is_hidden,
        )
    except catalog.CatalogEditError as exc:
        raise _rejected(exc) from exc


@router.delete("/categories/{category_id}")
async def delete_category(category_id: uuid.UUID, session: SessionDep) -> None:
    try:
        await catalog.delete_category(session, category_id)
    except catalog.CatalogEditError as exc:
        raise _rejected(exc) from exc


@router.post("/categories/order")
async def reorder_categories(body: OrderIn, session: SessionDep) -> None:
    try:
        await catalog.reorder_categories(session, body.ids)
    except catalog.CatalogEditError as exc:
        raise _rejected(exc) from exc


@router.post("/dishes")
async def create_dish(body: DishIn, session: SessionDep) -> CreatedOut:
    try:
        dish_id = await catalog.create_dish(session, _dish_input(body))
    except catalog.CatalogEditError as exc:
        raise _rejected(exc) from exc
    return CreatedOut(id=dish_id)


@router.put("/dishes/{dish_id}")
async def update_dish(dish_id: uuid.UUID, body: DishIn, session: SessionDep) -> None:
    try:
        await catalog.update_dish(session, dish_id, _dish_input(body))
    except catalog.CatalogEditError as exc:
        raise _rejected(exc) from exc


@router.delete("/dishes/{dish_id}")
async def delete_dish(dish_id: uuid.UUID, session: SessionDep) -> None:
    try:
        await catalog.delete_dish(session, dish_id)
    except catalog.CatalogEditError as exc:
        raise _rejected(exc) from exc


@router.post("/dishes/order")
async def reorder_dishes(body: DishOrderIn, session: SessionDep) -> None:
    try:
        await catalog.reorder_dishes(session, body.category_id, body.ids)
    except catalog.CatalogEditError as exc:
        raise _rejected(exc) from exc
