"""Kitchen load and preorder slots (FR-8, FR-37). Pure where it can be."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.locations import api as locations
from fenix.modules.ordering.models import Order

IN_WORK: frozenset[str] = frozenset({"new", "accepted", "cooking"})
# A preorder goes to the kitchen this long before its slot (story 5.5).
RELEASE_LEAD = timedelta(minutes=30)


@dataclass(frozen=True, slots=True)
class KitchenLoad:
    level: locations.LoadLevel
    in_work: int
    extra_minutes: int
    # What the guest is told: preparation time plus the level's extra.
    wait_minutes: int
    manual: bool
    manual_until: datetime | None


def level_for(in_work: int, settings: locations.OrderSettings) -> locations.LoadLevel:
    if in_work >= settings.load_busy_from:
        return "busy"
    if in_work >= settings.load_moderate_from:
        return "moderate"
    return "calm"


def load_from(in_work: int, settings: locations.OrderSettings) -> KitchenLoad:
    override = settings.kitchen_override
    level = override.level if override else level_for(in_work, settings)
    extra = {
        "calm": 0,
        "moderate": settings.load_moderate_extra,
        "busy": settings.load_busy_extra,
    }[level]
    return KitchenLoad(
        level=level,
        in_work=in_work,
        extra_minutes=extra,
        wait_minutes=settings.prep_minutes + extra,
        manual=override is not None,
        manual_until=override.until if override else None,
    )


async def kitchen_load(
    session: AsyncSession, location_id: uuid.UUID, settings: locations.OrderSettings
) -> KitchenLoad:
    in_work = (
        await session.execute(
            select(func.count())
            .select_from(Order)
            .where(Order.location_id == location_id, Order.status.in_(IN_WORK))
        )
    ).scalar_one()
    return load_from(in_work, settings)


def slots(settings: locations.OrderSettings, wait_minutes: int, now: datetime) -> list[datetime]:
    """Today's preorder slots: from now + waiting time, on the step grid, up to closing
    (local time of the location, AD-11). Empty while the location is closed."""
    if not settings.status.is_open:
        return []
    zone = ZoneInfo(settings.timezone)
    local_now = now.astimezone(zone)
    # Open round the clock: slots until the end of the local day.
    closes_at = settings.status.closes_at or (
        local_now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    )
    step = timedelta(minutes=settings.slot_step_minutes)
    earliest = local_now + timedelta(minutes=wait_minutes)
    midnight = earliest.replace(hour=0, minute=0, second=0, microsecond=0)
    # Round up to the grid counted from local midnight: 9:00, 9:15, 9:30…
    steps = -(-(earliest - midnight) // step)
    slot = midnight + steps * step
    result = []
    while slot <= closes_at:
        result.append(slot)
        slot += step
    return result
