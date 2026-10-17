"""Promotions managed by staff (FR-32). Mounted under /api/v1/staff."""

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from fenix.http.auth import LocationIdDep
from fenix.http.deps import SessionDep
from fenix.modules.catalog import api as catalog
from fenix.platform.errors import ApiError

router = APIRouter(prefix="/promotions", tags=["staff-promotions"])


class PromotionIn(BaseModel):
    title: str = Field(max_length=256, description="Text for guests")
    percent: int = Field(ge=1, le=100)
    # null: the whole menu.
    category_id: uuid.UUID | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    kind: Literal["auto", "checked"] = "auto"
    enabled: bool = True


class PromotionOut(PromotionIn):
    id: uuid.UUID


def _rejected(exc: catalog.PromotionError) -> ApiError:
    return ApiError(exc.status, exc.code, "The promotion was rejected")


def _input(body: PromotionIn) -> catalog.PromotionInput:
    return catalog.PromotionInput(**body.model_dump())


@router.get("")
async def list_promotions(session: SessionDep, location_id: LocationIdDep) -> list[PromotionOut]:
    return [
        PromotionOut(
            id=p.id,
            title=p.title,
            percent=p.percent,
            category_id=p.category_id,
            starts_on=p.starts_on,
            ends_on=p.ends_on,
            kind=p.kind,
            enabled=p.enabled,
        )
        for p in await catalog.list_promotions(session, location_id)
    ]


@router.post("")
async def create_promotion(
    body: PromotionIn, session: SessionDep, location_id: LocationIdDep
) -> PromotionOut:
    try:
        promotion_id = await catalog.create_promotion(session, location_id, _input(body))
    except catalog.PromotionError as exc:
        raise _rejected(exc) from exc
    return PromotionOut(id=promotion_id, **body.model_dump())


@router.put("/{promotion_id}")
async def update_promotion(
    promotion_id: uuid.UUID, body: PromotionIn, session: SessionDep, location_id: LocationIdDep
) -> PromotionOut:
    try:
        await catalog.update_promotion(session, location_id, promotion_id, _input(body))
    except catalog.PromotionError as exc:
        raise _rejected(exc) from exc
    return PromotionOut(id=promotion_id, **body.model_dump())


@router.delete("/{promotion_id}")
async def delete_promotion(
    promotion_id: uuid.UUID, session: SessionDep, location_id: LocationIdDep
) -> None:
    try:
        await catalog.delete_promotion(session, location_id, promotion_id)
    except catalog.PromotionError as exc:
        raise _rejected(exc) from exc
