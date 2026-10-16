"""Public API of `locations`: functions and DTOs, the only import surface for other modules."""

import uuid
from dataclasses import dataclass
from datetime import datetime, time
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.locations import hours, seed, service
from fenix.modules.locations.hours import OpeningStatus, format_time
from fenix.modules.locations.models import Location

__all__ = [
    "LocationInfo",
    "OpeningInterval",
    "OpeningStatus",
    "SocialLink",
    "format_time",
    "get_default_location",
    "seed_defaults",
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
    )


async def seed_defaults(session: AsyncSession) -> bool:
    """Idempotent initial data; returns True when something was created."""
    return await seed.seed_default_location(session)
