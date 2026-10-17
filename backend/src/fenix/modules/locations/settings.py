"""Order parameters of a location, pauses and the manual kitchen load (FR-30, FR-31, FR-37)."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.locations.editor import LocationEditError, _location

LoadLevel = Literal["calm", "moderate", "busy"]
SLOT_STEPS = frozenset({5, 10, 15, 20, 30, 60})


@dataclass(frozen=True, slots=True)
class OrderParams:
    prep_minutes: int
    slot_step_minutes: int
    unpaid_timeout_minutes: int
    delivery_enabled: bool
    delivery_fee: int
    load_moderate_from: int
    load_busy_from: int
    load_moderate_extra: int
    load_busy_extra: int


@dataclass(frozen=True, slots=True)
class Pauses:
    orders_paused: bool
    delivery_paused: bool


@dataclass(frozen=True, slots=True)
class KitchenOverride:
    level: LoadLevel
    # None: until cancelled.
    until: datetime | None


async def get_params(session: AsyncSession, location_id: uuid.UUID) -> OrderParams:
    location = await _location(session, location_id)
    return OrderParams(
        prep_minutes=location.prep_minutes,
        slot_step_minutes=location.slot_step_minutes,
        unpaid_timeout_minutes=location.unpaid_timeout_minutes,
        delivery_enabled=location.delivery_enabled,
        delivery_fee=location.delivery_fee,
        load_moderate_from=location.load_moderate_from,
        load_busy_from=location.load_busy_from,
        load_moderate_extra=location.load_moderate_extra,
        load_busy_extra=location.load_busy_extra,
    )


async def update_params(session: AsyncSession, location_id: uuid.UUID, data: OrderParams) -> None:
    """Applies to orders placed after saving (FR-31). Raises LocationEditError bad_params."""
    valid = (
        5 <= data.prep_minutes <= 180
        and data.slot_step_minutes in SLOT_STEPS
        and 5 <= data.unpaid_timeout_minutes <= 60
        and 0 <= data.delivery_fee <= 1_000_000
        and 1 <= data.load_moderate_from < data.load_busy_from <= 100
        and 0 <= data.load_moderate_extra <= data.load_busy_extra <= 180
    )
    if not valid:
        raise LocationEditError("bad_params")
    location = await _location(session, location_id)
    for name in OrderParams.__slots__:
        setattr(location, name, getattr(data, name))
    await session.flush()


async def set_pauses(
    session: AsyncSession,
    location_id: uuid.UUID,
    *,
    orders_paused: bool | None = None,
    delivery_paused: bool | None = None,
) -> Pauses:
    location = await _location(session, location_id)
    if orders_paused is not None:
        location.orders_paused = orders_paused
    if delivery_paused is not None:
        location.delivery_paused = delivery_paused
    await session.flush()
    return Pauses(location.orders_paused, location.delivery_paused)


async def set_kitchen_override(
    session: AsyncSession,
    location_id: uuid.UUID,
    level: LoadLevel | None,
    minutes: int | None,
    now: datetime,
) -> None:
    """A level by hand for 30 / 60 minutes or until cancelled; None returns to automatic."""
    location = await _location(session, location_id)
    location.kitchen_override = level
    location.kitchen_override_until = (
        now + timedelta(minutes=minutes) if level is not None and minutes else None
    )
    await session.flush()
