from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from fenix.http.deps import SessionDep
from fenix.http.media import photo_url
from fenix.modules.locations import api as locations
from fenix.modules.ordering import api as ordering
from fenix.platform.errors import ApiError

router = APIRouter(tags=["location"])


class OpeningStatusOut(BaseModel):
    is_open: bool
    text: str = Field(description="Ready to show, e.g. «Открыто до 22:00»")
    closes_at: datetime | None
    opens_at: datetime | None


class OpeningHoursOut(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0 = Monday")
    opens_at: str = Field(description="Local time, H:MM")
    closes_at: str = Field(description="Local time, H:MM; not after opens_at means past midnight")


class SocialLinkOut(BaseModel):
    kind: str
    title: str
    url: str


class LocationOut(BaseModel):
    name: str
    address: str
    map_url: str
    phone: str
    description: str
    social_links: list[SocialLinkOut]
    opening_hours: list[OpeningHoursOut]
    status: OpeningStatusOut
    photos: list[str] = Field(description="Cafe photo URLs under /media/")
    # «Готовим ≈M мин» (FR-37): preparation time plus the kitchen load's extra.
    wait_minutes: int
    kitchen_busy: bool
    orders_paused: bool


@router.get("/location")
async def get_location(session: SessionDep) -> LocationOut:
    now = datetime.now(UTC)
    info = await locations.get_default_location(session, now)
    location_id = await locations.get_default_location_id(session)
    if info is None or location_id is None:
        raise ApiError(404, "location_not_found", "No location is configured")
    load = await ordering.kitchen_load(session, location_id, now)
    settings = await locations.get_order_settings(session, location_id, now)
    return LocationOut(
        name=info.name,
        address=info.address,
        map_url=info.map_url,
        phone=info.phone,
        description=info.description,
        social_links=[
            SocialLinkOut(kind=s.kind, title=s.title, url=s.url) for s in info.social_links
        ],
        opening_hours=[
            OpeningHoursOut(
                weekday=h.weekday,
                opens_at=locations.format_time(h.opens_at),
                closes_at=locations.format_time(h.closes_at),
            )
            for h in info.opening_hours
        ],
        photos=[url for key in info.photo_keys if (url := photo_url(key))],
        wait_minutes=load.wait_minutes,
        kitchen_busy=load.level == "busy",
        orders_paused=settings.orders_paused,
        status=OpeningStatusOut(
            is_open=info.status.is_open,
            text=info.status.text,
            closes_at=info.status.closes_at,
            opens_at=info.status.opens_at,
        ),
    )
