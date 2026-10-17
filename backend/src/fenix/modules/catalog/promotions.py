"""Promotions (FR-5, FR-11, FR-32): at most one per line — the largest discount (AD-6)."""

import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fenix.modules.catalog.models import Category, Promotion
from fenix.modules.locations import api as locations

Kind = Literal["auto", "checked"]
BIRTHDAY_TITLE = "В день рождения — скидка 10% на всё меню"


class PromotionError(Exception):
    def __init__(self, code: str, status: int = 422) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass(frozen=True, slots=True)
class PromotionView:
    id: uuid.UUID
    title: str
    percent: int
    category_id: uuid.UUID | None
    starts_on: date | None
    ends_on: date | None
    kind: str
    enabled: bool


@dataclass(frozen=True, slots=True)
class PromotionInput:
    title: str
    percent: int
    category_id: uuid.UUID | None
    starts_on: date | None
    ends_on: date | None
    kind: Kind
    enabled: bool


def _view(row: Promotion) -> PromotionView:
    return PromotionView(
        row.id,
        row.title,
        row.percent,
        row.category_id,
        row.starts_on,
        row.ends_on,
        row.kind,
        row.enabled,
    )


def discounted(unit_price: int, percent: int) -> int:
    """Rounded to whole rubles, as on a price tag."""
    return (unit_price * (100 - percent) + 5000) // 10000 * 100


async def local_today(session: AsyncSession, location_id: uuid.UUID) -> date:
    now = datetime.now(UTC)
    settings = await locations.get_order_settings(session, location_id, now)
    return now.astimezone(ZoneInfo(settings.timezone)).date()


async def active(session: AsyncSession, location_id: uuid.UUID, today: date) -> list[PromotionView]:
    """Enabled and within dates today; an expired one stops by itself (FR-5)."""
    statement = select(Promotion).where(
        Promotion.location_id == location_id,
        Promotion.enabled.is_(True),
        or_(Promotion.starts_on.is_(None), Promotion.starts_on <= today),
        or_(Promotion.ends_on.is_(None), Promotion.ends_on >= today),
    )
    return [_view(row) for row in (await session.execute(statement)).scalars()]


def best_for(
    promotions: list[PromotionView], category_id: uuid.UUID, claimed: uuid.UUID | None
) -> PromotionView | None:
    """Automatic ones plus the claimed «checked» one compete; the largest wins."""
    candidates = [
        p
        for p in promotions
        if (p.kind == "auto" or p.id == claimed)
        and (p.category_id is None or p.category_id == category_id)
    ]
    return max(candidates, key=lambda p: p.percent, default=None)


async def list_all(session: AsyncSession, location_id: uuid.UUID) -> list[PromotionView]:
    statement = (
        select(Promotion).where(Promotion.location_id == location_id).order_by(Promotion.created_at)
    )
    return [_view(row) for row in (await session.execute(statement)).scalars()]


async def _validate(session: AsyncSession, data: PromotionInput) -> None:
    if not 1 <= data.percent <= 100:
        raise PromotionError("bad_percent")
    if data.starts_on and data.ends_on and data.ends_on < data.starts_on:
        raise PromotionError("bad_dates")
    if not data.title.strip():
        raise PromotionError("title_required")
    if data.kind not in ("auto", "checked"):
        raise PromotionError("bad_kind")
    if data.category_id and await session.get(Category, data.category_id) is None:
        raise PromotionError("category_not_found", 404)


async def create(session: AsyncSession, location_id: uuid.UUID, data: PromotionInput) -> uuid.UUID:
    await _validate(session, data)
    row = Promotion(location_id=location_id, **{**asdict(data), "title": data.title.strip()})
    session.add(row)
    await session.flush()
    return row.id


async def update(
    session: AsyncSession, location_id: uuid.UUID, promotion_id: uuid.UUID, data: PromotionInput
) -> None:
    row = await session.get(Promotion, promotion_id)
    if row is None or row.location_id != location_id:
        raise PromotionError("promotion_not_found", 404)
    await _validate(session, data)
    for name, value in asdict(data).items():
        setattr(row, name, value.strip() if name == "title" else value)
    await session.flush()


async def delete(session: AsyncSession, location_id: uuid.UUID, promotion_id: uuid.UUID) -> None:
    row = await session.get(Promotion, promotion_id)
    if row is None or row.location_id != location_id:
        raise PromotionError("promotion_not_found", 404)
    await session.delete(row)
    await session.flush()


async def seed_birthday(session: AsyncSession, location_id: uuid.UUID) -> bool:
    """The birthday discount exists from the start (FR-32); idempotent."""
    exists = await session.execute(
        select(Promotion.id).where(
            Promotion.location_id == location_id, Promotion.kind == "checked"
        )
    )
    if exists.first():
        return False
    session.add(
        Promotion(
            location_id=location_id,
            title=BIRTHDAY_TITLE,
            percent=10,
            category_id=None,
            kind="checked",
            enabled=True,
        )
    )
    await session.flush()
    return True
