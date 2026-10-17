"""Orders and their lifecycle (AD-3): one transition function over an explicit table."""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.catalog import api as catalog
from fenix.modules.identity import api as identity
from fenix.modules.locations import api as locations
from fenix.modules.ordering import cart, kitchen
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
Fulfilment = Literal["pickup", "delivery"]


@dataclass(frozen=True, slots=True)
class Address:
    house: str
    apartment: str
    entrance: str = ""
    floor: str = ""
    comment: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "house": self.house.strip()[:64],
            "apartment": self.apartment.strip()[:16],
            "entrance": self.entrance.strip()[:16],
            "floor": self.floor.strip()[:16],
            "comment": self.comment.strip()[:300],
        }


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
    # A paid preorder waits for its slot instead of going to the kitchen (story 5.5).
    ("pending_payment", "schedule"): _rule("scheduled", "system"),
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
    "schedule": "payment_confirmed",
    "release": "released",
    "accept": "accepted",
    "start_cooking": "cooking_started",
    "mark_ready": "ready",
    "hand_over": "handed_over",
    "dispatch": "dispatched",
    "deliver": "delivered",
    "cancel": "cancelled",
    "confirm_discount": "discount_confirmed",
    "reject_discount": "discount_rejected",
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
    original_unit_price: int = 0
    promotion_title: str | None = None


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
    delivery_fee: int = 0
    address: dict[str, str] | None = None
    change_from: int | None = None
    scheduled_for: datetime | None = None
    discount_claim: dict[str, object] | None = None
    discount_status: str | None = None
    total_without_claim: int | None = None
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
            OrderLine(
                i.title,
                list(i.modifier_names),
                i.quantity,
                i.unit_price,
                i.total_price,
                i.original_unit_price or i.unit_price,
                i.promotion_title,
            )
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
        delivery_fee=order.delivery_fee,
        address=order.address,
        change_from=order.change_from,
        scheduled_for=order.scheduled_for,
        discount_claim=order.discount_claim,
        discount_status=order.discount_status,
        total_without_claim=order.total_without_claim,
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
            "scheduled_for": order.scheduled_for.isoformat() if order.scheduled_for else None,
            "delivery_fee": order.delivery_fee,
            "address": order.address,
            "change_from": order.change_from,
            "discount_claim": order.discount_claim,
            "discount_status": order.discount_status,
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
    fulfilment: Fulfilment = "pickup",
    address: Address | None = None,
    change_from: int | None = None,
    scheduled_for: datetime | None = None,
    claimed_promotion_id: uuid.UUID | None = None,
) -> OrderView:
    settings = await locations.get_order_settings(session, location_id, now)
    if not settings.status.is_open:
        raise OrderError("location_closed", details={"status": settings.status.text})
    if settings.orders_paused:
        raise OrderError("orders_paused")
    if fulfilment == "delivery":
        if not settings.delivery_enabled or settings.delivery_paused:
            raise OrderError("delivery_unavailable")
        if address is None or not address.house.strip() or not address.apartment.strip():
            raise OrderError("address_required")
    if scheduled_for is not None:
        load = await kitchen.kitchen_load(session, location_id, settings)
        available = kitchen.slots(settings, load.wait_minutes, now)
        if scheduled_for not in available:
            raise OrderError(
                "slot_unavailable",
                details={"slots": [slot.isoformat() for slot in available[:4]]},
            )
    contact = await identity.get_contact(session, user_id)
    if not contact.phone or not contact.has_consent:
        raise OrderError("contact_required")

    claim: dict[str, object] | None = None
    if claimed_promotion_id is not None:
        promotion = next(
            (
                p
                for p in await catalog.active_promotions(session, location_id)
                if p.id == claimed_promotion_id and p.kind == "checked"
            ),
            None,
        )
        if promotion is None:
            raise OrderError("promotion_unavailable")
        # The discount is confirmed at the counter: no online payment (FR-11).
        if payment_method == "online":
            raise OrderError("claim_requires_on_site")
        claim = {
            "promotion_id": str(promotion.id),
            "title": promotion.title,
            "percent": promotion.percent,
        }

    current = await cart.view(session, user_id, location_id, claimed_promotion_id)
    if not current.lines:
        raise OrderError("empty_cart")
    if any(line.problem for line in current.lines):
        raise OrderError("cart_has_unavailable")
    without = await cart.view(session, user_id, location_id) if claim else current

    delivery_fee = settings.delivery_fee if fulfilment == "delivery" else 0
    total = current.total + delivery_fee
    claimed_line = {line.id: line for line in without.lines}
    if change_from is not None and (payment_method != "cash" or change_from < total):
        raise OrderError("bad_change")

    day = business_date(now, settings.timezone)
    status: Status = (
        "pending_payment"
        if payment_method == "online"
        else ("scheduled" if scheduled_for else "new")
    )
    order = Order(
        location_id=location_id,
        user_id=user_id,
        number=await next_number(session, location_id, day),
        business_date=day,
        status=status,
        version=1,
        fulfilment=fulfilment,
        address=address.as_dict() if fulfilment == "delivery" and address else None,
        change_from=change_from,
        delivery_fee=delivery_fee,
        scheduled_for=scheduled_for,
        ready_at=scheduled_for,
        payment_method=payment_method,
        comment=comment.strip()[:500],
        customer_name=contact.first_name,
        customer_phone=contact.phone,
        phone_verified=contact.phone_verified,
        total=total,
        discount_claim=claim,
        discount_status="pending" if claim else None,
        total_without_claim=without.total + delivery_fee if claim else None,
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
                original_unit_price=line.original_unit_price or line.unit_price or 0,
                promotion_title=line.promotion_title,
                discount_percent=line.discount_percent,
                unit_price_without_claim=(claimed_line[line.id].unit_price if claim else None),
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
    # A claimed discount is decided before the order leaves the counter (FR-23).
    if action in ("hand_over", "deliver") and order.discount_status == "pending":
        raise OrderError("discount_decision_required")

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


async def due_scheduled(session: AsyncSession, now: datetime) -> list[uuid.UUID]:
    """Preorders whose slot is near enough to go to the kitchen (story 5.5)."""
    statement = select(Order.id).where(
        Order.status == "scheduled", Order.scheduled_for <= now + kitchen.RELEASE_LEAD
    )
    return list((await session.execute(statement)).scalars())


async def decide_discount(
    session: AsyncSession,
    order_id: uuid.UUID,
    confirm: bool,
    actor: Actor,
    *,
    expected_version: int,
    now: datetime,
) -> OrderView:
    """Staff confirm the claimed discount or remove it; the total is recalculated and the
    decision logged (FR-23). Raises order_not_found, no_discount_claim, order_conflict."""
    order = await session.get(Order, order_id)
    if order is None:
        raise OrderError("order_not_found", 404)
    if order.discount_status != "pending" or order.status in FINAL:
        raise OrderError("no_discount_claim")
    if order.version != expected_version:
        raise OrderError("order_conflict", 409)
    action = "confirm_discount" if confirm else "reject_discount"
    changed = await session.execute(
        update(Order)
        .where(Order.id == order_id, Order.version == expected_version)
        .values(
            version=expected_version + 1,
            updated_at=now,
            discount_status="confirmed" if confirm else "rejected",
            total=order.total if confirm else order.total_without_claim,
        )
        .returning(Order.id)
        .execution_options(synchronize_session=False)
    )
    if changed.first() is None:
        raise OrderError("order_conflict", 409)
    if not confirm:
        for item in order.items:
            if item.unit_price_without_claim is not None:
                item.unit_price = item.unit_price_without_claim
                item.total_price = item.unit_price_without_claim * item.quantity
                if item.promotion_title == (order.discount_claim or {}).get("title"):
                    item.promotion_title = None
                    item.discount_percent = 0
    session.add(
        OrderEvent(
            order_id=order_id,
            action=action,
            from_status=order.status,
            to_status=order.status,
            actor_kind=actor.kind,
            actor_user_id=actor.user_id,
        )
    )
    await session.flush()
    await session.refresh(order)
    decided = view(order)
    await emit_event(session, decided, action, actor.kind)
    return decided
