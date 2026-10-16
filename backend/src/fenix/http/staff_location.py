"""Staff editing of the cafe (FR-30, FR-33). Mounted under /api/v1/staff."""

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel, Field

from fenix.http.auth import LocationIdDep
from fenix.http.deps import SessionDep
from fenix.http.media import StorageDep, photo_url
from fenix.modules.locations import api as locations
from fenix.platform.errors import ApiError

router = APIRouter(tags=["staff-location"])


class HoursIn(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0 = Monday")
    opens_at: str = Field(description="H:MM")
    closes_at: str = Field(description="H:MM; not after opens_at means past midnight")


class SocialLinkIn(BaseModel):
    kind: str = Field(default="link", max_length=32)
    title: str = Field(max_length=64)
    url: str = Field(max_length=512)


class LocationIn(BaseModel):
    address: str = Field(max_length=512)
    latitude: float | None = None
    longitude: float | None = None
    phone: str = Field(max_length=32)
    description: str = Field(default="", max_length=2000)
    social_links: list[SocialLinkIn] = Field(default_factory=list, max_length=10)
    opening_hours: list[HoursIn] = Field(max_length=7)


class PhotosOut(BaseModel):
    photos: list[str]


def _rejected(exc: locations.LocationEditError) -> ApiError:
    return ApiError(exc.status, exc.code, "The cafe change was rejected")


@router.put("/location")
async def update_location(
    body: LocationIn, session: SessionDep, location_id: LocationIdDep
) -> None:
    data = locations.LocationInput(
        address=body.address,
        latitude=body.latitude,
        longitude=body.longitude,
        phone=body.phone,
        description=body.description,
        social_links=[locations.SocialLinkInput(s.kind, s.title, s.url) for s in body.social_links],
        opening_hours=[
            locations.HoursInput(h.weekday, h.opens_at, h.closes_at) for h in body.opening_hours
        ],
    )
    try:
        await locations.update_location(session, location_id, data)
    except locations.LocationEditError as exc:
        raise _rejected(exc) from exc


@router.post("/location/photos")
async def add_photo(
    file: UploadFile, session: SessionDep, location_id: LocationIdDep, storage: StorageDep
) -> PhotosOut:
    data = await file.read(locations.MAX_PHOTO_BYTES + 1)
    try:
        key, webp = await locations.prepare_photo(location_id, data)
        await storage.put(key, webp, "image/webp")
        keys = await locations.add_photo(session, location_id, key)
    except locations.LocationEditError as exc:
        raise _rejected(exc) from exc
    return PhotosOut(photos=[url for k in keys if (url := photo_url(k))])


@router.delete("/location/photos")
async def remove_photo(key: str, session: SessionDep, location_id: LocationIdDep) -> PhotosOut:
    try:
        keys = await locations.remove_photo(session, location_id, key.removeprefix("/media/"))
    except locations.LocationEditError as exc:
        raise _rejected(exc) from exc
    return PhotosOut(photos=[url for k in keys if (url := photo_url(k))])
