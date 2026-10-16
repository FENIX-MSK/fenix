"""The guest's orders."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from fenix.http.auth import CurrentUser, LocationIdDep
from fenix.http.checkout import PaymentMethod
from fenix.http.deps import SessionDep
from fenix.modules.ordering import api as ordering
from fenix.platform.errors import ApiError

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderLineOut(BaseModel):
    title: str
    modifier_names: list[str]
    quantity: int
    unit_price: int
    total_price: int


class OrderOut(BaseModel):
    id: uuid.UUID
    number: str = Field(description="«#047»")
    status: str
    version: int
    fulfilment: str
    payment_method: str
    payment_status: str = Field(description="unpaid, paid or refunded")
    comment: str
    total: int
    created_at: datetime
    ready_at: datetime | None
    lines: list[OrderLineOut]


class PlaceIn(BaseModel):
    payment_method: PaymentMethod
    comment: str = Field(default="", max_length=500)


def order_out(order: ordering.OrderView, payment_status: str = "unpaid") -> OrderOut:
    return OrderOut(
        id=order.id,
        number=order.label,
        status=order.status,
        version=order.version,
        fulfilment=order.fulfilment,
        payment_method=order.payment_method,
        payment_status=payment_status,
        comment=order.comment,
        total=order.total,
        created_at=order.created_at,
        ready_at=order.ready_at,
        lines=[
            OrderLineOut(
                title=line.title,
                modifier_names=line.modifier_names,
                quantity=line.quantity,
                unit_price=line.unit_price,
                total_price=line.total_price,
            )
            for line in order.lines
        ],
    )


@router.post("")
async def place_order(
    body: PlaceIn, user: CurrentUser, session: SessionDep, location_id: LocationIdDep
) -> OrderOut:
    try:
        order = await ordering.place_order(
            session,
            user.id,
            location_id,
            payment_method=body.payment_method,
            comment=body.comment,
            now=datetime.now(UTC),
        )
    except ordering.OrderError as exc:
        raise ApiError(exc.status, exc.code, "The order was rejected", dict(exc.details)) from exc
    return order_out(order)


@router.get("/{order_id}")
async def get_order(order_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> OrderOut:
    order = await ordering.get_order(session, order_id)
    # Someone else's order looks exactly like a missing one.
    if order is None or order.user_id != user.id:
        raise ApiError(404, "order_not_found", "No such order")
    return order_out(order)
