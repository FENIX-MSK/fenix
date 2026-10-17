import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from fenix.http.auth import CurrentUser, LocationIdDep
from fenix.http.deps import SessionDep
from fenix.http.media import photo_url
from fenix.modules.ordering import api as ordering
from fenix.platform.errors import ApiError

router = APIRouter(prefix="/cart", tags=["cart"])


class CartLineOut(BaseModel):
    id: uuid.UUID
    dish_id: uuid.UUID
    title: str
    modifier_names: list[str]
    quantity: int
    photo_url: str | None
    unit_price: int | None = Field(description="Kopecks; null when the line cannot be ordered")
    total_price: int | None
    available: bool
    problem: str | None


class CartOut(BaseModel):
    lines: list[CartLineOut]
    total: int = Field(description="Kopecks of the lines that can be ordered")
    count: int


class AddIn(BaseModel):
    dish_id: uuid.UUID
    size_id: uuid.UUID
    modifier_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    quantity: int = Field(ge=1, le=99)


class QuantityIn(BaseModel):
    quantity: int = Field(ge=0, le=99, description="0 removes the line")


def cart_out(view: ordering.CartView) -> CartOut:
    return CartOut(
        lines=[
            CartLineOut(
                id=line.id,
                dish_id=line.dish_id,
                title=line.title,
                modifier_names=line.modifier_names,
                quantity=line.quantity,
                photo_url=photo_url(line.photo_key),
                unit_price=line.unit_price,
                total_price=line.total_price,
                available=line.problem is None,
                problem=line.problem,
            )
            for line in view.lines
        ],
        total=view.total,
        count=view.count,
    )


def _rejected(exc: ordering.CartError) -> ApiError:
    return ApiError(exc.status, exc.code, "The cart change was rejected", exc.details)


@router.get("")
async def get_cart(user: CurrentUser, session: SessionDep, location_id: LocationIdDep) -> CartOut:
    return cart_out(await ordering.view_cart(session, user.id, location_id))


@router.post("/items")
async def add_item(
    body: AddIn, user: CurrentUser, session: SessionDep, location_id: LocationIdDep
) -> CartOut:
    try:
        await ordering.add_to_cart(
            session,
            user.id,
            location_id,
            dish_id=body.dish_id,
            size_id=body.size_id,
            modifier_ids=body.modifier_ids,
            quantity=body.quantity,
        )
    except ordering.CartError as exc:
        raise _rejected(exc) from exc
    return cart_out(await ordering.view_cart(session, user.id, location_id))


@router.patch("/items/{item_id}")
async def set_quantity(
    item_id: uuid.UUID,
    body: QuantityIn,
    user: CurrentUser,
    session: SessionDep,
    location_id: LocationIdDep,
) -> CartOut:
    try:
        await ordering.set_cart_quantity(session, user.id, location_id, item_id, body.quantity)
    except ordering.CartError as exc:
        raise _rejected(exc) from exc
    return cart_out(await ordering.view_cart(session, user.id, location_id))


@router.delete("/items/{item_id}")
async def remove_item(
    item_id: uuid.UUID, user: CurrentUser, session: SessionDep, location_id: LocationIdDep
) -> CartOut:
    try:
        await ordering.remove_from_cart(session, user.id, location_id, item_id)
    except ordering.CartError as exc:
        raise _rejected(exc) from exc
    return cart_out(await ordering.view_cart(session, user.id, location_id))
