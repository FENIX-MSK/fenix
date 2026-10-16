"""Orders and their lifecycle (AD-3): one transition function over an explicit table."""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.identity import api as identity
from fenix.modules.locations import api as locations
from fenix.modules.ordering import cart
from fenix.modules.ordering.models import Order, OrderCounter, OrderEvent, OrderItem

Status = Literal[
    "pending_payment",
    "scheduled",
    "new",
    "accepted",
    "cooking",
    "ready",
    "handed_over",
    "delivering",
    "delivered",
    "cancelled",
]
ActorKind = Literal["guest", "staff", "system"]
PaymentMethod = Literal["online", "cash", "card"]

ACTIVE: frozenset[str] = frozenset({"new", "accepted", "cooking", "ready", "delivering"})
FINAL: frozenset[str] = frozenset({"handed_over", "delivered", "cancelled"})


@dataclass(frozen=True, slots=True)
class Rule:
    to: Status
    actors: frozenset[ActorKind]
    fulfilment: str | None = None


def _rule(to: Status, *actors: ActorKind, fulfilment: str | None = None) -> Rule:
    return Rule(to, frozenset(actors), fulfilment)


# (from status, action) -> rule. Anything not listed is not allowed (AD-3 diagram).
TRANSITIONS: dict[tuple[str, str], Rule] = {
    ("pending_payment", "payment_succeeded"): _rule("new", "system"),
    ("pending_payment", "cancel"): _rule("cancelled", "system"),
    ("scheduled", "release"): _rule("new", "system"),
    ("scheduled", "cancel"): _rule("cancelled", "staff", "system"),
    ("new", "accept"): _rule("accepted", "staff"),
    ("new", "cancel"): _rule("cancelled", "staff"),
    ("accepted", "start_cooking"): _rule("cooking", "staff"),
    ("accepted", "cancel"): _rule("cancelled", "staff"),
    ("cooking", "mark_ready"): _rule("ready", "staff"),
    ("cooking", "cancel"): _rule("cancelled", "staff"),
    ("ready", "hand_over"): _rule("handed_over", "staff", fulfilment="pickup"),
    ("ready", "dispatch"): _rule("delivering", "staff", fulfilment="delivery"),
    ("ready", "cancel"): _rule("cancelled", "staff"),
    ("delivering", "deliver"): _rule("delivered", "staff"),
}


class OrderError(Exception):
    def __init__(
        self, code: str, status: int = 422, details: dict[str, object] | None = None
    ) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
        self.details = details or {}


@dataclass(frozen=True, slots=True)
class Actor:
    kind: ActorKind
    user_id: uuid.UUID | None = None


SYSTEM = Actor("system")


@dataclass(frozen=True, slots=True)
class OrderLine:
    title: str
    modifier_names: list[str]
    quantity: int
    unit_price: int
    total_price: int


@dataclass(frozen=True, slots=True)
class LogEntry:
    at: datetime
    action: str
    from_status: str | None
    to_status: str
    actor_kind: str
    actor_user_id: uuid.UUID | None
    note: str | None


@dataclass(frozen=True, slots=True)
class OrderView:
    id: uuid.UUID
    location_id: uuid.UUID
    user_id: uuid.UUID
    number: int
    status: str
    version: int
    fulfilment: str
    payment_method: str
    comment: str
    customer_name: str
    customer_phone: str
    phone_verified: bool
    total: int
    created_at: datetime
    ready_at: datetime | None
    lines: list[OrderLine]
    log: list[LogEntry] = field(default_factory=list)
    # Internal, for staff only.
    cancel_reason: str | None = None

    @property
    def label(self) -> str:
        return f"#{self.number:03d}"


def view(order: Order) -> OrderView:
    return OrderView(
        id=order.id,
        location_id=order.location_id,
        user_id=order.user_id,
        number=order.number,
        status=order.status,
        version=order.version,
        fulfilment=order.fulfilment,
        payment_method=order.payment_method,
        comment=order.comment,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        phone_verified=order.phone_verified,
        total=order.total,
        created_at=order.created_at,
        ready_at=order.ready_at,
        lines=[
            OrderLine(i.title, list(i.modifier_names), i.quantity, i.unit_price, i.total_price)
            for i in order.items
        ],
        log=[
            LogEntry(
                e.created_at,
                e.action,
                e.from_status,
                e.to_status,
                e.actor_kind,
                e.actor_user_id,
                e.note,
            )
            for e in order.events
        ],
        cancel_reason=order.cancel_reason,
    )


async def next_number(session: AsyncSession, location_id: uuid.UUID, business_date: date) -> int:
    """Atomic: the upsert takes the counter row's lock until the transaction ends."""
    statement = (
        insert(OrderCounter)
        .values(location_id=location_id, business_date=business_date, last_number=1)
        .on_conflict_do_update(
            index_elements=[OrderCounter.location_id, OrderCounter.business_date],
            set_={"last_number": OrderCounter.last_number + 1},
        )
        .returning(OrderCounter.last_number)
    )
    return (await session.execute(statement)).scalar_one()


def business_date(now: datetime, timezone: str) -> date:
    return now.astimezone(ZoneInfo(timezone)).date()


async def place(
    session: AsyncSession,
    user_id: uuid.UUID,
    location_id: uuid.UUID,
    *,
    payment_method: PaymentMethod,
    comment: str,
    now: datetime,
) -> OrderView:
    settings = await locations.get_order_settings(session, location_id, now)
    if not settings.status.is_open:
        raise OrderError("location_closed", details={"status": settings.status.text})
    contact = await identity.get_contact(session, user_id)
    if not contact.phone or not contact.has_consent:
        raise OrderError("contact_required")

    current = await cart.view(session, user_id, location_id)
    if not current.lines:
        raise OrderError("empty_cart")
    if any(line.problem for line in current.lines):
        raise OrderError("cart_has_unavailable")

    day = business_date(now, settings.timezone)
    status: Status = "pending_payment" if payment_method == "online" else "new"
    order = Order(
        location_id=location_id,
        user_id=user_id,
        number=await next_number(session, location_id, day),
        business_date=day,
        status=status,
        version=1,
        fulfilment="pickup",
        payment_method=payment_method,
        comment=comment.strip()[:500],
        customer_name=contact.first_name,
        customer_phone=contact.phone,
        phone_verified=contact.phone_verified,
        total=current.total,
        items=[
            OrderItem(
                position=position,
                dish_id=line.dish_id,
                size_id=line.size_id,
                modifier_ids=[str(m) for m in line.modifier_ids],
                title=line.title,
                modifier_names=line.modifier_names,
                quantity=line.quantity,
                unit_price=line.unit_price or 0,
                total_price=line.total_price or 0,
            )
            for position, line in enumerate(current.lines)
        ],
        events=[
            OrderEvent(
                action="create",
                from_status=None,
                to_status=status,
                actor_kind="guest",
                actor_user_id=user_id,
            )
        ],
    )
    session.add(order)
    await cart.clear(session, user_id, location_id)
    await session.flush()
    await session.refresh(order, ["created_at", "items", "events"])
    return view(order)


async def get(session: AsyncSession, order_id: uuid.UUID) -> Order | None:
    return await session.get(Order, order_id)


async def transition(
    session: AsyncSession,
    order_id: uuid.UUID,
    action: str,
    actor: Actor,
    *,
    expected_version: int | None,
    now: datetime,
    ready_at: datetime | None = None,
    note: str | None = None,
) -> OrderView:
    """The only way to change an order's status (AD-3).

    `expected_version` None is for system actors that act on whatever is current.
    Raises OrderError: order_not_found (404), transition_not_allowed (422),
    order_conflict (409), reason_required (422).
    """
    order = await session.get(Order, order_id)
    if order is None:
        raise OrderError("order_not_found", 404)
    rule = TRANSITIONS.get((order.status, action))
    if (
        rule is None
        or actor.kind not in rule.actors
        or (rule.fulfilment is not None and rule.fulfilment != order.fulfilment)
    ):
        raise OrderError(
            "transition_not_allowed", details={"status": order.status, "action": action}
        )
    if action == "cancel" and actor.kind == "staff" and not (note and note.strip()):
        raise OrderError("reason_required")

    version = expected_version if expected_version is not None else order.version
    values: dict[str, object] = {"status": rule.to, "version": version + 1, "updated_at": now}
    if action == "accept":
        values["ready_at"] = ready_at
    if action == "cancel":
        values["cancel_reason"] = note.strip() if note else None
    # Compare-and-set on the version: of two simultaneous actions the first one wins.
    changed = await session.execute(
        update(Order)
        .where(Order.id == order_id, Order.version == version, Order.status == order.status)
        .values(**values)
        .returning(Order.id)
        .execution_options(synchronize_session=False)
    )
    if changed.first() is None:
        raise OrderError("order_conflict", 409)
    session.add(
        OrderEvent(
            order_id=order_id,
            action=action,
            from_status=order.status,
            to_status=rule.to,
            actor_kind=actor.kind,
            actor_user_id=actor.user_id,
            note=note.strip() if note else None,
        )
    )
    await session.flush()
    await session.refresh(order)
    return view(order)


def default_ready_at(now: datetime, prep_minutes: int) -> datetime:
    return now + timedelta(minutes=prep_minutes)


async def count_in_status(
    session: AsyncSession, location_id: uuid.UUID, statuses: frozenset[str]
) -> int:
    statement = (
        select(func.count())
        .select_from(Order)
        .where(Order.location_id == location_id, Order.status.in_(statuses))
    )
    return (await session.execute(statement)).scalar_one()
