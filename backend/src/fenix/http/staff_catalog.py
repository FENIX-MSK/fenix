"""Staff menu editor (FR-26). Mounted under /api/v1/staff, so every route needs staff."""

import uuid

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel, Field

from fenix.http.deps import SessionDep
from fenix.http.media import StorageDep, photo_url
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


class OptionIn(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field(max_length=128)
    price_delta: int = Field(default=0, ge=0, le=10_000_000, description="Kopecks")


class GroupIn(BaseModel):
    name: str = Field(max_length=128)
    min_choice: int = Field(ge=0, le=50)
    max_choice: int = Field(ge=1, le=50)
    options: list[OptionIn] = Field(max_length=50)


class LinksIn(BaseModel):
    dish_ids: list[uuid.UUID] = Field(default_factory=list)
    category_ids: list[uuid.UUID] = Field(default_factory=list)


class OptionOut(BaseModel):
    id: uuid.UUID
    name: str
    price_delta: int


class GroupOut(BaseModel):
    id: uuid.UUID
    name: str
    min_choice: int
    max_choice: int
    options: list[OptionOut]
    dish_ids: list[uuid.UUID]
    category_ids: list[uuid.UUID]


def _group_input(body: GroupIn) -> catalog.GroupInput:
    return catalog.GroupInput(
        name=body.name,
        min_choice=body.min_choice,
        max_choice=body.max_choice,
        options=[catalog.OptionInput(o.id, o.name, o.price_delta) for o in body.options],
    )


@router.get("/modifier-groups")
async def list_groups(session: SessionDep) -> list[GroupOut]:
    return [
        GroupOut(
            id=g.id,
            name=g.name,
            min_choice=g.min_choice,
            max_choice=g.max_choice,
            options=[OptionOut(id=o.id, name=o.name, price_delta=o.price_delta) for o in g.options],
            dish_ids=g.links.dish_ids,
            category_ids=g.links.category_ids,
        )
        for g in await catalog.list_groups(session)
    ]


@router.post("/modifier-groups")
async def create_group(body: GroupIn, session: SessionDep) -> CreatedOut:
    try:
        group_id = await catalog.create_group(session, _group_input(body))
    except catalog.CatalogEditError as exc:
        raise _rejected(exc) from exc
    return CreatedOut(id=group_id)


@router.put("/modifier-groups/{group_id}")
async def update_group(group_id: uuid.UUID, body: GroupIn, session: SessionDep) -> None:
    try:
        await catalog.update_group(session, group_id, _group_input(body))
    except catalog.CatalogEditError as exc:
        raise _rejected(exc) from exc


@router.delete("/modifier-groups/{group_id}")
async def delete_group(group_id: uuid.UUID, session: SessionDep) -> None:
    try:
        await catalog.delete_group(session, group_id)
    except catalog.CatalogEditError as exc:
        raise _rejected(exc) from exc


@router.put("/modifier-groups/{group_id}/links")
async def set_links(group_id: uuid.UUID, body: LinksIn, session: SessionDep) -> None:
    try:
        await catalog.set_group_links(
            session, group_id, catalog.GroupLinks(body.dish_ids, body.category_ids)
        )
    except catalog.CatalogEditError as exc:
        raise _rejected(exc) from exc


class PhotoOut(BaseModel):
    photo_url: str


@router.post("/dishes/{dish_id}/photo")
async def upload_dish_photo(
    dish_id: uuid.UUID, file: UploadFile, session: SessionDep, storage: StorageDep
) -> PhotoOut:
    data = await file.read(catalog.MAX_PHOTO_BYTES + 1)
    try:
        key, webp = await catalog.prepare_dish_photo(dish_id, data)
        # Stored first: a failed upload leaves the old photo on the dish (EXPERIENCE.md).
        await storage.put(key, webp, "image/webp")
        await catalog.set_dish_photo(session, dish_id, key)
    except catalog.CatalogEditError as exc:
        raise ApiError(exc.status, exc.code, "The photo was rejected") from exc
    return PhotoOut(photo_url=f"/media/{key}")


@router.delete("/dishes/{dish_id}/photo")
async def delete_dish_photo(dish_id: uuid.UUID, session: SessionDep) -> None:
    try:
        await catalog.set_dish_photo(session, dish_id, None)
    except catalog.CatalogEditError as exc:
        raise _rejected(exc) from exc
