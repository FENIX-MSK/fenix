"""Staff editing of the location: hours, contacts, description, photos (FR-30, FR-33)."""

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fenix.modules.locations.models import Location, OpeningHours

MAX_PHOTOS = 10
_TIME = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


class LocationEditError(Exception):
    def __init__(self, code: str, status: int = 422) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass(frozen=True, slots=True)
class HoursInput:
    weekday: int
    opens_at: str
    closes_at: str


@dataclass(frozen=True, slots=True)
class SocialLinkInput:
    kind: str
    title: str
    url: str


@dataclass(frozen=True, slots=True)
class LocationInput:
    address: str
    latitude: float | None
    longitude: float | None
    phone: str
    description: str
    social_links: Sequence[SocialLinkInput]
    # A weekday left out is a day off.
    opening_hours: Sequence[HoursInput]


def parse_time(text: str) -> time:
    match = _TIME.match(text.strip())
    if not match:
        raise LocationEditError("bad_time")
    return time(int(match[1]), int(match[2]))


async def _location(session: AsyncSession, location_id: uuid.UUID) -> Location:
    location = (
        await session.execute(
            select(Location)
            .where(Location.id == location_id)
            .options(selectinload(Location.opening_hours))
        )
    ).scalar_one_or_none()
    if location is None:
        raise LocationEditError("location_not_found", 404)
    return location


async def update_location(
    session: AsyncSession, location_id: uuid.UUID, data: LocationInput
) -> None:
    if not data.address.strip() or not data.phone.strip():
        raise LocationEditError("contacts_required")
    if (data.latitude is None) != (data.longitude is None) or not (
        data.latitude is None or (-90 <= data.latitude <= 90 and -180 <= data.longitude <= 180)  # type: ignore[operator]
    ):
        raise LocationEditError("bad_coordinates")
    if any(
        not link.url.startswith("https://") or not link.title.strip() for link in data.social_links
    ):
        raise LocationEditError("bad_social_link")
    weekdays = [hours.weekday for hours in data.opening_hours]
    if len(set(weekdays)) != len(weekdays) or any(not 0 <= day <= 6 for day in weekdays):
        raise LocationEditError("bad_weekday")
    hours = [
        (h.weekday, parse_time(h.opens_at), parse_time(h.closes_at)) for h in data.opening_hours
    ]

    location = await _location(session, location_id)
    location.address = data.address.strip()
    location.latitude, location.longitude = data.latitude, data.longitude
    location.phone = data.phone.strip()
    location.description = data.description.strip()
    location.social_links = [
        {"kind": link.kind.strip() or "link", "title": link.title.strip(), "url": link.url.strip()}
        for link in data.social_links
    ]
    # Closing at or before opening means after midnight; equal times — 24 hours (1.3).
    existing = {row.weekday: row for row in location.opening_hours}
    rows = []
    for weekday, opens_at, closes_at in sorted(hours):
        row = existing.get(weekday) or OpeningHours(weekday=weekday)
        row.opens_at, row.closes_at = opens_at, closes_at
        rows.append(row)
    location.opening_hours = rows
    await session.flush()


async def add_photo(session: AsyncSession, location_id: uuid.UUID, key: str) -> list[str]:
    location = await _location(session, location_id)
    if len(location.photo_keys) >= MAX_PHOTOS:
        raise LocationEditError("too_many_photos")
    # A new list: JSONB columns notice reassignment, not in-place appends.
    location.photo_keys = [*location.photo_keys, key]
    await session.flush()
    return location.photo_keys


async def remove_photo(session: AsyncSession, location_id: uuid.UUID, key: str) -> list[str]:
    location = await _location(session, location_id)
    if key not in location.photo_keys:
        raise LocationEditError("photo_not_found", 404)
    location.photo_keys = [k for k in location.photo_keys if k != key]
    await session.flush()
    return location.photo_keys


def new_photo_key(location_id: uuid.UUID) -> str:
    return f"cafe/{location_id}/{uuid.uuid7()}.webp"
