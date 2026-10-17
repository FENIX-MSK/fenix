"""Sales report (FR-36): computed from `ordering`, `payments` and `identity` APIs (AD-2)."""

import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.identity import api as identity
from fenix.modules.locations import api as locations
from fenix.modules.ordering import api as ordering
from fenix.modules.payments import api as payments

# The synthetic account of the post-deploy smoke test (fenix.smoke.SMOKE_USER).
TECHNICAL_USERS = {"1"}
REVENUE_STATUSES = frozenset({"handed_over", "delivered"})


@dataclass(frozen=True, slots=True)
class DishSales:
    title: str
    quantity: int
    revenue: int


@dataclass(frozen=True, slots=True)
class SalesReport:
    start: date
    end: date  # inclusive
    revenue: int
    completed: int
    orders: int
    average_check: int
    cancelled: int
    by_payment: dict[str, int] = field(default_factory=dict)
    by_fulfilment: dict[str, int] = field(default_factory=dict)
    top_dishes: list[DishSales] = field(default_factory=list)
    cancel_reasons: dict[str, int] = field(default_factory=dict)
    new_guests: dict[str, int] = field(default_factory=dict)


def bounds(start: date, end: date, zone: str) -> tuple[datetime, datetime]:
    """Local midnights of the location (AD-11): [start 00:00, day after end 00:00)."""
    tz = ZoneInfo(zone)
    return (
        datetime.combine(start, time(0), tz),
        datetime.combine(end + timedelta(days=1), time(0), tz),
    )


async def sales_report(
    session: AsyncSession, location_id: uuid.UUID, start: date, end: date, now: datetime
) -> SalesReport:
    settings = await locations.get_order_settings(session, location_id, now)
    since, until = bounds(start, end, settings.timezone)
    technical: set[uuid.UUID] = set()
    for external_id in TECHNICAL_USERS:
        user = await identity.find_user(session, identity.Platform.TELEGRAM, external_id)
        if user:
            technical.add(user.id)
    orders = [
        o
        for o in await ordering.orders_between(session, location_id, since, until)
        if o.user_id not in technical and o.status != "pending_payment"
    ]
    paid = await payments.order_payments(session, [o.id for o in orders])
    done = [o for o in orders if o.status in REVENUE_STATUSES]
    revenue = sum(o.total for o in done)

    by_payment: Counter[str] = Counter()
    by_fulfilment: Counter[str] = Counter()
    dishes: dict[str, list[int]] = {}
    for order in done:
        projection = paid[order.id]
        by_payment[projection.method or order.payment_method] += order.total
        by_fulfilment[order.fulfilment] += 1
        for line in order.lines:
            entry = dishes.setdefault(line.title, [0, 0])
            entry[0] += line.quantity
            entry[1] += line.total_price
    cancelled = [o for o in orders if o.status == "cancelled"]
    reasons = Counter((o.cancel_reason or "без причины") for o in cancelled)
    top = sorted(dishes.items(), key=lambda item: (-item[1][0], -item[1][1]))[:10]
    return SalesReport(
        start=start,
        end=end,
        revenue=revenue,
        completed=len(done),
        orders=len(orders),
        average_check=revenue // len(done) if done else 0,
        cancelled=len(cancelled),
        by_payment=dict(by_payment),
        by_fulfilment=dict(by_fulfilment),
        top_dishes=[DishSales(title, q, r) for title, (q, r) in top],
        cancel_reasons=dict(reasons),
        new_guests=await identity.new_users_by_source(session, since, until, TECHNICAL_USERS),
    )
