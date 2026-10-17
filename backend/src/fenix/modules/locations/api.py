"""Public API of `locations`: functions and DTOs, the only import surface for other modules."""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, time
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.locations import editor, hours, seed, service, settings
from fenix.modules.locations.editor import (
    HoursInput,
    LocationEditError,
    LocationInput,
    SocialLinkInput,
)
from fenix.modules.locations.hours import OpeningStatus, format_time
from fenix.modules.locations.models import Location
from fenix.modules.locations.settings import KitchenOverride, LoadLevel, OrderParams, Pauses
from fenix.platform import outbox
from fenix.platform.images import MAX_UPLOAD_BYTES as MAX_PHOTO_BYTES
from fenix.platform.images import ImageRejectedError, shrink

__all__ = [
    "MAX_PHOTO_BYTES",
    "HoursInput",
    "KitchenOverride",
    "LoadLevel",
    "LocationEditError",
    "LocationInfo",
    "LocationInput",
    "OpeningInterval",
    "OpeningStatus",
    "OrderParams",
    "OrderSettings",
    "Pauses",
    "SocialLink",
    "SocialLinkInput",
    "add_photo",
    "format_time",
    "get_default_location",
    "get_default_location_id",
    "get_order_params",
    "get_order_settings",
    "prepare_photo",
    "remove_photo",
    "seed_defaults",
    "set_kitchen_override",
    "set_pauses",
    "update_location",
    "update_order_params",
]


@dataclass(frozen=True, slots=True)
class SocialLink:
    kind: str
    title: str
    url: str


@dataclass(frozen=True, slots=True)
class OpeningInterval:
    weekday: int
    opens_at: time
    closes_at: time


@dataclass(frozen=True, slots=True)
class LocationInfo:
    id: uuid.UUID
    name: str
    timezone: str
    address: str
    map_url: str
    phone: str
    description: str
    social_links: list[SocialLink]
    opening_hours: list[OpeningInterval]
    status: OpeningStatus
    photo_keys: list[str]


def _map_url(location: Location) -> str:
    if location.latitude is not None and location.longitude is not None:
        return f"https://yandex.ru/maps/?pt={location.longitude},{location.latitude}&z=17&l=map"
    return f"https://yandex.ru/maps/?text={quote(location.address)}"


async def get_default_location(session: AsyncSession, now: datetime) -> LocationInfo | None:
    location = await service.get_default_location(session)
    if location is None:
        return None
    intervals = [
        hours.Interval(row.weekday, row.opens_at, row.closes_at) for row in location.opening_hours
    ]
    return LocationInfo(
        id=location.id,
        name=location.name,
        timezone=location.timezone,
        address=location.address,
        map_url=_map_url(location),
        phone=location.phone,
        description=location.description,
        social_links=[
            SocialLink(kind=link["kind"], title=link["title"], url=link["url"])
            for link in location.social_links
        ],
        opening_hours=[OpeningInterval(i.weekday, i.opens_at, i.closes_at) for i in intervals],
        status=hours.opening_status(intervals, location.timezone, now),
        photo_keys=list(location.photo_keys),
    )


async def get_default_location_id(session: AsyncSession) -> uuid.UUID | None:
    location = await service.get_default_location(session)
    return location.id if location else None


async def seed_defaults(session: AsyncSession) -> bool:
    """Idempotent initial data; returns True when something was created."""
    return await seed.seed_default_location(session)


async def update_location(
    session: AsyncSession, location_id: uuid.UUID, data: LocationInput
) -> None:
    """Replace contacts, description, links and the weekly hours. Raises LocationEditError."""
    await editor.update_location(session, location_id, data)


async def prepare_photo(location_id: uuid.UUID, data: bytes) -> tuple[str, bytes]:
    """A new key and the shrunk WebP. Raises LocationEditError for a rejected image."""
    try:
        webp = await asyncio.to_thread(shrink, data)
    except ImageRejectedError as exc:
        raise LocationEditError(exc.code) from exc
    return editor.new_photo_key(location_id), webp


async def add_photo(session: AsyncSession, location_id: uuid.UUID, key: str) -> list[str]:
    return await editor.add_photo(session, location_id, key)


async def remove_photo(session: AsyncSession, location_id: uuid.UUID, key: str) -> list[str]:
    return await editor.remove_photo(session, location_id, key)


@dataclass(frozen=True, slots=True)
class OrderSettings:
    timezone: str
    prep_minutes: int
    unpaid_timeout_minutes: int
    status: OpeningStatus
    slot_step_minutes: int = 15
    delivery_enabled: bool = True
    delivery_fee: int = 0
    orders_paused: bool = False
    delivery_paused: bool = False
    load_moderate_from: int = 4
    load_busy_from: int = 8
    load_moderate_extra: int = 10
    load_busy_extra: int = 20
    # The manual kitchen level, if one is in force at `now`.
    kitchen_override: KitchenOverride | None = None


async def get_order_settings(
    session: AsyncSession, location_id: uuid.UUID, now: datetime
) -> OrderSettings:
    location = await service.get_default_location(session)
    if location is None or location.id != location_id:
        # One location for now; the explicit id keeps callers honest for later.
        raise LookupError(location_id)
    intervals = [
        hours.Interval(row.weekday, row.opens_at, row.closes_at) for row in location.opening_hours
    ]
    override = None
    if location.kitchen_override and (
        location.kitchen_override_until is None or location.kitchen_override_until > now
    ):
        override = KitchenOverride(location.kitchen_override, location.kitchen_override_until)  # type: ignore[arg-type]
    return OrderSettings(
        timezone=location.timezone,
        prep_minutes=location.prep_minutes,
        unpaid_timeout_minutes=location.unpaid_timeout_minutes,
        status=hours.opening_status(intervals, location.timezone, now),
        slot_step_minutes=location.slot_step_minutes,
        delivery_enabled=location.delivery_enabled,
        delivery_fee=location.delivery_fee,
        orders_paused=location.orders_paused,
        delivery_paused=location.delivery_paused,
        load_moderate_from=location.load_moderate_from,
        load_busy_from=location.load_busy_from,
        load_moderate_extra=location.load_moderate_extra,
        load_busy_extra=location.load_busy_extra,
        kitchen_override=override,
    )


async def get_order_params(session: AsyncSession, location_id: uuid.UUID) -> OrderParams:
    return await settings.get_params(session, location_id)


async def update_order_params(
    session: AsyncSession, location_id: uuid.UUID, data: OrderParams
) -> None:
    """Raises LocationEditError bad_params."""
    await settings.update_params(session, location_id, data)


async def set_pauses(
    session: AsyncSession,
    location_id: uuid.UUID,
    *,
    orders_paused: bool | None = None,
    delivery_paused: bool | None = None,
) -> Pauses:
    """«Приём заказов приостановлен» / «Доставка приостановлена» (FR-30)."""
    return await settings.set_pauses(
        session, location_id, orders_paused=orders_paused, delivery_paused=delivery_paused
    )


async def set_kitchen_override(
    session: AsyncSession,
    location_id: uuid.UUID,
    level: LoadLevel | None,
    minutes: int | None,
    now: datetime,
) -> None:
    """Emits `locations.kitchen.load_changed` so every board updates at once."""
    await settings.set_kitchen_override(session, location_id, level, minutes, now)
    outbox.emit(session, "locations.kitchen.load_changed", {"location_id": str(location_id)})
