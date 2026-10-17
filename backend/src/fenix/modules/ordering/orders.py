"""Orders and their lifecycle (AD-3): one transition function over an explicit table."""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.identity import api as identity
from fenix.modules.locations import api as locations
from fenix.modules.ordering import cart
from fenix.modules.ordering.models import Order, OrderCounter, OrderEvent, OrderItem
from fenix.platform import outbox

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


# Domain event per action: `ordering.order.<past_tense>` (AD-4).
EVENT_NAMES: dict[str, str] = {
    "create": "placed",
    "payment_succeeded": "payment_confirmed",
    "release": "released",
    "accept": "accepted",
    "start_cooking": "cooking_started",
    "mark_ready": "ready",
    "hand_over": "handed_over",
    "dispatch": "dispatched",
    "deliver": "delivered",
    "cancel": "cancelled",
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


async def emit_event(
    session: AsyncSession,
    order: OrderView,
    action: str,
    actor: ActorKind,
    extra: dict[str, object] | None = None,
) -> None:
    """Everything subscribers need, so they never call back into ordering (AD-4)."""
    user = await identity.get_user(session, order.user_id)
    timezone = (
        await locations.get_order_settings(session, order.location_id, order.created_at)
    ).timezone
    outbox.emit(
        session,
        f"ordering.order.{EVENT_NAMES[action]}",
        {
            "order_id": str(order.id),
            "location_id": str(order.location_id),
            "number": order.label,
            "status": order.status,
            "version": order.version,
            "actor": actor,
            "fulfilment": order.fulfilment,
            "payment_method": order.payment_method,
            "total": order.total,
            "comment": order.comment,
            "ready_at": order.ready_at.isoformat() if order.ready_at else None,
            "timezone": timezone,
            "lines": [
                {
                    "title": line.title,
                    "modifier_names": line.modifier_names,
                    "quantity": line.quantity,
                    "total_price": line.total_price,
                }
                for line in order.lines
            ],
            "customer": {
                "user_id": str(order.user_id),
                "platform": user.platform.value if user else None,
                "external_id": user.external_id if user else None,
                "name": order.customer_name,
            },
            **(extra or {}),
        },
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
    placed = view(order)
    await emit_event(session, placed, "create", "guest")
    return placed


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
    event_extra: dict[str, object] | None = None,
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
    changed_view = view(order)
    await emit_event(session, changed_view, action, actor.kind, event_extra)
    return changed_view


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


async def overdue_unpaid(session: AsyncSession, now: datetime) -> list[uuid.UUID]:
    """Orders left in `pending_payment` past their location's timeout (FR-13)."""
    rows = (
        await session.execute(
            select(Order.id, Order.location_id, Order.created_at).where(
                Order.status == "pending_payment"
            )
        )
    ).all()
    timeouts: dict[uuid.UUID, int] = {}
    overdue = []
    for order_id, location_id, created_at in rows:
        if location_id not in timeouts:
            settings = await locations.get_order_settings(session, location_id, now)
            timeouts[location_id] = settings.unpaid_timeout_minutes
        if created_at + timedelta(minutes=timeouts[location_id]) <= now:
            overdue.append(order_id)
    return overdue


async def list_orders(
    session: AsyncSession, location_id: uuid.UUID, statuses: frozenset[str]
) -> list[OrderView]:
    statement = (
        select(Order)
        .where(Order.location_id == location_id, Order.status.in_(statuses))
        .order_by(Order.created_at)
    )
    return [view(order) for order in (await session.execute(statement)).scalars()]


ACTIVE_FOR_GUEST: frozenset[str] = frozenset(
    {"pending_payment", "scheduled", "new", "accepted", "cooking", "ready", "delivering"}
)


async def guest_orders(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int,
    before: tuple[datetime, uuid.UUID] | None = None,
) -> list[OrderView]:
    """The guest's orders, newest first; keyset pages by (created_at, id)."""
    statement = select(Order).where(Order.user_id == user_id)
    if before is not None:
        statement = statement.where(tuple_(Order.created_at, Order.id) < tuple_(*before))
    statement = statement.order_by(Order.created_at.desc(), Order.id.desc()).limit(limit)
    return [view(order) for order in (await session.execute(statement)).scalars()]


async def active_guest_order(session: AsyncSession, user_id: uuid.UUID) -> OrderView | None:
    statement = (
        select(Order)
        .where(Order.user_id == user_id, Order.status.in_(ACTIVE_FOR_GUEST))
        .order_by(Order.created_at.desc())
        .limit(1)
    )
    order = (await session.execute(statement)).scalar_one_or_none()
    return view(order) if order else None


@dataclass(frozen=True, slots=True)
class RepeatResult:
    added: int
    skipped: list[str]


async def repeat(
    session: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID, location_id: uuid.UUID
) -> RepeatResult:
    """Put the order's lines back into the cart at today's prices (FR-18). Lines that are
    gone from the menu or stopped are skipped and named."""
    order = await session.get(Order, order_id)
    if order is None or order.user_id != user_id:
        raise OrderError("order_not_found", 404)
    added, skipped = 0, []
    for item in order.items:
        try:
            async with session.begin_nested():
                await cart.add(
                    session,
                    user_id,
                    location_id,
                    dish_id=item.dish_id,
                    size_id=item.size_id,
                    modifier_ids=[uuid.UUID(m) for m in item.modifier_ids],
                    quantity=item.quantity,
                )
            added += 1
        except cart.CartError:
            skipped.append(item.title)
    return RepeatResult(added, skipped)
