"""The order board and order handling by staff (FR-20 to FR-22, FR-25)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from fenix.http.auth import CurrentStaff, LocationIdDep
from fenix.http.deps import SessionDep
from fenix.http.orders import AddressOut, OrderLineOut, lines_out, order_error, payment_error
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
    delivery_fee: int
    address: AddressOut | None
    change_from: int | None
    scheduled_for: datetime | None
    # «День рождения — проверить документ» while pending (FR-23).
    discount_title: str | None
    discount_status: str | None
    total_without_claim: int | None
    # Internal (FR-22): staff see the reason, guests never do.
    cancel_reason: str | None
    log: list[LogEntryOut] = Field(default_factory=list)


class KitchenOut(BaseModel):
    level: Literal["calm", "moderate", "busy"]
    in_work: int
    wait_minutes: int
    manual: bool
    # A manual level ends at this moment; null with `manual` = until cancelled.
    manual_until: datetime | None


class BoardOut(BaseModel):
    orders: list[StaffOrderOut]
    prep_minutes: int
    timezone: str
    kitchen: KitchenOut


class KitchenIn(BaseModel):
    # null: back to the automatic level.
    level: Literal["calm", "moderate", "busy"] | None
    # 30, 60 or null (until cancelled).
    minutes: Literal[30, 60] | None = None


def kitchen_out(load: ordering.KitchenLoad) -> KitchenOut:
    return KitchenOut(
        level=load.level,
        in_work=load.in_work,
        wait_minutes=load.wait_minutes,
        manual=load.manual,
        manual_until=load.manual_until,
    )


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


class DiscountIn(BaseModel):
    confirm: bool
    expected_version: int


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
        delivery_fee=order.delivery_fee,
        address=AddressOut(**order.address) if order.address else None,
        change_from=order.change_from,
        scheduled_for=order.scheduled_for,
        discount_title=str(order.discount_claim["title"]) if order.discount_claim else None,
        discount_status=order.discount_status,
        total_without_claim=order.total_without_claim,
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
    now = datetime.now(UTC)
    settings = await locations.get_order_settings(session, location_id, now)
    return BoardOut(
        orders=[staff_order_out(order, paid[order.id]) for order in orders],
        prep_minutes=settings.prep_minutes,
        timezone=settings.timezone,
        kitchen=kitchen_out(await ordering.kitchen_load(session, location_id, now)),
    )


@router.post("/kitchen")
async def set_kitchen(
    body: KitchenIn, session: SessionDep, location_id: LocationIdDep
) -> KitchenOut:
    """The manual kitchen level (FR-37); every board hears about it at once."""
    now = datetime.now(UTC)
    await locations.set_kitchen_override(session, location_id, body.level, body.minutes, now)
    return kitchen_out(await ordering.kitchen_load(session, location_id, now))


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
        # A preorder is due at its slot, not earlier (story 5.5).
        if order.scheduled_for and order.scheduled_for > ready_at:
            ready_at = order.scheduled_for
    if not ordering.is_allowed(order, body.action, "staff"):
        raise ApiError(
            422,
            "transition_not_allowed",
            "This action is not available now",
            {"status": order.status, "action": body.action},
        )
    if body.action in ("hand_over", "deliver") and payment.status != "paid":
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


@router.post("/{order_id}/discount")
async def decide_discount(
    order_id: uuid.UUID,
    body: DiscountIn,
    staff: CurrentStaff,
    session: SessionDep,
    location_id: LocationIdDep,
) -> StaffOrderOut:
    """Confirm the claimed discount after checking the document, or remove it (FR-23)."""
    order = await location_order(session, order_id, location_id)
    try:
        decided = await ordering.decide_discount(
            session,
            order.id,
            body.confirm,
            ordering.Actor("staff", staff.id),
            expected_version=body.expected_version,
            now=datetime.now(UTC),
        )
    except ordering.OrderError as exc:
        raise order_error(exc) from exc
    return await detailed(session, decided)
