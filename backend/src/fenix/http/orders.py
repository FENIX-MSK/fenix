"""The guest's orders and their online payment (FR-12, FR-13)."""

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from fenix.http.auth import CurrentUser, LocationIdDep
from fenix.http.checkout import PaymentMethod
from fenix.http.deps import SessionDep
from fenix.modules.ordering import api as ordering
from fenix.modules.payments import api as payments
from fenix.platform.errors import ApiError

router = APIRouter(tags=["orders"])


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
    payment_status: Literal["unpaid", "pending", "failed", "paid", "refunded"]
    # The online attempt the guest can still complete (test payment screen).
    payment_id: uuid.UUID | None
    comment: str
    total: int
    created_at: datetime
    ready_at: datetime | None
    lines: list[OrderLineOut]


class PlaceIn(BaseModel):
    payment_method: PaymentMethod
    comment: str = Field(default="", max_length=500)


class TestPaymentIn(BaseModel):
    succeeded: bool


def lines_out(order: ordering.OrderView) -> list[OrderLineOut]:
    return [
        OrderLineOut(
            title=line.title,
            modifier_names=line.modifier_names,
            quantity=line.quantity,
            unit_price=line.unit_price,
            total_price=line.total_price,
        )
        for line in order.lines
    ]


def order_out(order: ordering.OrderView, payment: payments.OrderPayment) -> OrderOut:
    return OrderOut(
        id=order.id,
        number=order.label,
        status=order.status,
        version=order.version,
        fulfilment=order.fulfilment,
        payment_method=order.payment_method,
        payment_status=payment.status,
        payment_id=payment.pending_payment_id if order.status == "pending_payment" else None,
        comment=order.comment,
        total=order.total,
        created_at=order.created_at,
        ready_at=order.ready_at,
        lines=lines_out(order),
    )


def order_error(exc: ordering.OrderError) -> ApiError:
    return ApiError(exc.status, exc.code, "The order was rejected", dict(exc.details))


def payment_error(exc: payments.PaymentError) -> ApiError:
    return ApiError(exc.status, exc.code, "The payment was rejected")


async def own_order(
    session: SessionDep, order_id: uuid.UUID, user: CurrentUser
) -> ordering.OrderView:
    order = await ordering.get_order(session, order_id)
    # Someone else's order looks exactly like a missing one.
    if order is None or order.user_id != user.id:
        raise ApiError(404, "order_not_found", "No such order")
    return order


async def present(session: SessionDep, order: ordering.OrderView) -> OrderOut:
    return order_out(order, await payments.order_payment(session, order.id))


@router.post("/orders")
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
        raise order_error(exc) from exc
    if order.status == "pending_payment":
        await payments.start_online(
            session, order.id, location_id, order.total, f"Заказ {order.label}"
        )
    return await present(session, order)


@router.get("/orders/{order_id}")
async def get_order(order_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> OrderOut:
    return await present(session, await own_order(session, order_id, user))


@router.post("/orders/{order_id}/payments")
async def retry_payment(order_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> OrderOut:
    """«Повторить» after a failed online payment: a new attempt."""
    order = await own_order(session, order_id, user)
    if order.status != "pending_payment":
        raise ApiError(409, "payment_not_expected", "The order is not waiting for payment")
    try:
        await payments.start_online(
            session, order.id, order.location_id, order.total, f"Заказ {order.label}"
        )
    except payments.PaymentError as exc:
        raise payment_error(exc) from exc
    return await present(session, order)


@router.post("/payments/{payment_id}/test-result")
async def test_payment_result(
    payment_id: uuid.UUID, body: TestPaymentIn, user: CurrentUser, session: SessionDep
) -> OrderOut:
    """The test provider (AD-9): the guest says whether the payment «went through»."""
    payment = await payments.get_payment(session, payment_id)
    if payment is None:
        raise ApiError(404, "payment_not_found", "No such payment")
    order = await own_order(session, payment.order_id, user)
    try:
        await payments.complete_test_payment(session, payment_id, body.succeeded, datetime.now(UTC))
    except payments.PaymentError as exc:
        raise payment_error(exc) from exc
    return await present(session, order)
