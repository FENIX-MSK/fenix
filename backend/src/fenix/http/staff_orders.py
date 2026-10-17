"""The order board and order handling by staff (FR-20 to FR-22, FR-25)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from fenix.http.auth import CurrentStaff, LocationIdDep
from fenix.http.deps import SessionDep
from fenix.http.orders import OrderLineOut, lines_out, order_error, payment_error
from fenix.modules.identity import api as identity
from fenix.modules.locations import api as locations
from fenix.modules.ordering import api as ordering
from fenix.modules.payments import api as payments
from fenix.platform.errors import ApiError

router = APIRouter(prefix="/orders", tags=["staff-orders"])

# What the board shows: everything the kitchen still has to do something with.
BOARD = frozenset({"new", "accepted", "cooking", "ready", "delivering", "scheduled"})
Action = Literal[
    "accept", "start_cooking", "mark_ready", "hand_over", "dispatch", "deliver", "cancel"
]
OnSite = Literal["cash", "card"]


class LogEntryOut(BaseModel):
    at: datetime
    action: str
    from_status: str | None
    to_status: str
    actor_kind: str
    actor_name: str | None
    note: str | None


class StaffOrderOut(BaseModel):
    id: uuid.UUID
    number: str
    status: str
    version: int
    fulfilment: str
    payment_method: str
    payment_status: str
    paid_with: str | None
    comment: str
    customer_name: str
    customer_phone: str
    phone_verified: bool
    total: int
    created_at: datetime
    ready_at: datetime | None
    lines: list[OrderLineOut]
    # Internal (FR-22): staff see the reason, guests never do.
    cancel_reason: str | None
    log: list[LogEntryOut] = Field(default_factory=list)


class BoardOut(BaseModel):
    orders: list[StaffOrderOut]
    prep_minutes: int
    timezone: str


class ActionIn(BaseModel):
    action: Action
    expected_version: int
    # accept: when it will be ready; default now + the location's preparation time.
    ready_at: datetime | None = None
    # cancel: the reason, required (FR-22).
    note: str | None = Field(default=None, max_length=500)
    # hand_over of an order paid at the counter: how it was paid (FR-14).
    paid_with: OnSite | None = None


class PaymentIn(BaseModel):
    method: OnSite


def staff_order_out(
    order: ordering.OrderView,
    payment: payments.OrderPayment,
    names: dict[uuid.UUID, str] | None = None,
) -> StaffOrderOut:
    names = names or {}
    return StaffOrderOut(
        id=order.id,
        number=order.label,
        status=order.status,
        version=order.version,
        fulfilment=order.fulfilment,
        payment_method=order.payment_method,
        payment_status=payment.status,
        paid_with=payment.method if payment.status in ("paid", "refunded") else None,
        comment=order.comment,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        phone_verified=order.phone_verified,
        total=order.total,
        created_at=order.created_at,
        ready_at=order.ready_at,
        lines=lines_out(order),
        cancel_reason=order.cancel_reason,
        log=[
            LogEntryOut(
                at=entry.at,
                action=entry.action,
                from_status=entry.from_status,
                to_status=entry.to_status,
                actor_kind=entry.actor_kind,
                actor_name=names.get(entry.actor_user_id) if entry.actor_user_id else None,
                note=entry.note,
            )
            for entry in order.log
        ],
    )


async def location_order(
    session: SessionDep, order_id: uuid.UUID, location_id: uuid.UUID
) -> ordering.OrderView:
    order = await ordering.get_order(session, order_id)
    if order is None or order.location_id != location_id:
        raise ApiError(404, "order_not_found", "No such order")
    return order


async def detailed(session: SessionDep, order: ordering.OrderView) -> StaffOrderOut:
    names: dict[uuid.UUID, str] = {}
    for entry in order.log:
        if entry.actor_user_id and entry.actor_user_id not in names:
            user = await identity.get_user(session, entry.actor_user_id)
            if user:
                names[entry.actor_user_id] = user.first_name
    return staff_order_out(order, await payments.order_payment(session, order.id), names)


@router.get("")
async def board(session: SessionDep, location_id: LocationIdDep) -> BoardOut:
    orders = await ordering.list_orders(session, location_id, BOARD)
    paid = await payments.order_payments(session, [order.id for order in orders])
    settings = await locations.get_order_settings(session, location_id, datetime.now(UTC))
    return BoardOut(
        orders=[staff_order_out(order, paid[order.id]) for order in orders],
        prep_minutes=settings.prep_minutes,
        timezone=settings.timezone,
    )


@router.get("/{order_id}")
async def order_card(
    order_id: uuid.UUID, session: SessionDep, location_id: LocationIdDep
) -> StaffOrderOut:
    return await detailed(session, await location_order(session, order_id, location_id))


@router.post("/{order_id}/actions")
async def act(
    order_id: uuid.UUID,
    body: ActionIn,
    staff: CurrentStaff,
    session: SessionDep,
    location_id: LocationIdDep,
) -> StaffOrderOut:
    """Raises 409 order_conflict when someone else changed the order first."""
    now = datetime.now(UTC)
    order = await location_order(session, order_id, location_id)
    payment = await payments.order_payment(session, order.id)
    ready_at = body.ready_at
    extra: dict[str, object] = {}
    if body.action == "accept" and ready_at is None:
        settings = await locations.get_order_settings(session, location_id, now)
        ready_at = now + timedelta(minutes=settings.prep_minutes)
    if body.action == "hand_over" and payment.status != "paid":
        if body.paid_with is None:
            raise ApiError(422, "payment_required", "Mark how the order was paid")
        try:
            await payments.record_on_site(
                session,
                order.id,
                location_id,
                method=body.paid_with,
                amount=order.total,
                user_id=staff.id,
                now=now,
            )
        except payments.PaymentError as exc:
            raise payment_error(exc) from exc
    if body.action == "cancel":
        # The guest is told the money comes back; the refund itself is the
        # `payments.refund` outbox handler, retried until the provider agrees (FR-15).
        extra["refunded"] = payment.status == "paid" and payment.method == "online"
    try:
        changed = await ordering.transition(
            session,
            order.id,
            body.action,
            ordering.Actor("staff", staff.id),
            expected_version=body.expected_version,
            now=now,
            ready_at=ready_at,
            note=body.note,
            event_extra=extra,
        )
    except ordering.OrderError as exc:
        raise order_error(exc) from exc
    return await detailed(session, changed)


@router.post("/{order_id}/payment")
async def mark_paid(
    order_id: uuid.UUID,
    body: PaymentIn,
    staff: CurrentStaff,
    session: SessionDep,
    location_id: LocationIdDep,
) -> StaffOrderOut:
    """«Оплачено наличными / картой» (FR-14)."""
    order = await location_order(session, order_id, location_id)
    if order.status in ("cancelled", "pending_payment"):
        raise ApiError(409, "payment_not_expected", "This order cannot be paid at the counter")
    try:
        await payments.record_on_site(
            session,
            order.id,
            location_id,
            method=body.method,
            amount=order.total,
            user_id=staff.id,
            now=datetime.now(UTC),
        )
    except payments.PaymentError as exc:
        raise payment_error(exc) from exc
    return await detailed(session, order)
