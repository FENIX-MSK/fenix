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


class OrderParamsIo(BaseModel):
    """Order parameters (FR-31); applied to orders placed after saving."""

    prep_minutes: int = Field(ge=5, le=180)
    slot_step_minutes: int
    unpaid_timeout_minutes: int = Field(ge=5, le=60)
    delivery_enabled: bool
    delivery_fee: int = Field(ge=0, description="kopecks")
    load_moderate_from: int
    load_busy_from: int
    load_moderate_extra: int
    load_busy_extra: int


class PausesIo(BaseModel):
    orders_paused: bool | None = None
    delivery_paused: bool | None = None


@router.get("/location/order-params")
async def get_order_params(session: SessionDep, location_id: LocationIdDep) -> OrderParamsIo:
    params = await locations.get_order_params(session, location_id)
    return OrderParamsIo(**{name: getattr(params, name) for name in OrderParamsIo.model_fields})


@router.put("/location/order-params")
async def update_order_params(
    body: OrderParamsIo, session: SessionDep, location_id: LocationIdDep
) -> OrderParamsIo:
    try:
        await locations.update_order_params(
            session, location_id, locations.OrderParams(**body.model_dump())
        )
    except locations.LocationEditError as exc:
        raise _rejected(exc) from exc
    return body


@router.get("/location/pauses")
async def get_pauses(session: SessionDep, location_id: LocationIdDep) -> PausesIo:
    pauses = await locations.set_pauses(session, location_id)
    return PausesIo(orders_paused=pauses.orders_paused, delivery_paused=pauses.delivery_paused)


@router.put("/location/pauses")
async def set_pauses(body: PausesIo, session: SessionDep, location_id: LocationIdDep) -> PausesIo:
    """«Приём заказов приостановлен» / «Доставка приостановлена» (FR-30)."""
    pauses = await locations.set_pauses(
        session,
        location_id,
        orders_paused=body.orders_paused,
        delivery_paused=body.delivery_paused,
    )
    return PausesIo(orders_paused=pauses.orders_paused, delivery_paused=pauses.delivery_paused)
