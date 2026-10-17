import uuid
from datetime import datetime, time
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fenix.platform.db import Base


class Location(Base):
    __tablename__ = "locations_locations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    name: Mapped[str] = mapped_column(String(128))
    # IANA zone; all business time of the location is computed in it (AD-11).
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    address: Mapped[str] = mapped_column(String(512))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    phone: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text, default="")
    # [{"kind": "telegram", "title": "Telegram", "url": "https://t.me/..."}], in display order.
    social_links: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # Order settings (FR-31; editable in epic 5): default cooking time and how long an
    # online order may stay unpaid.
    prep_minutes: Mapped[int] = mapped_column(SmallInteger, default=20, server_default="20")
    unpaid_timeout_minutes: Mapped[int] = mapped_column(
        SmallInteger, default=15, server_default="15"
    )
    # Preorder slots for today, every N minutes (FR-8).
    slot_step_minutes: Mapped[int] = mapped_column(SmallInteger, default=15, server_default="15")
    # Delivery inside the residential complex for a fixed fee in kopecks (FR-7).
    delivery_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    delivery_fee: Mapped[int] = mapped_column(Integer, default=15000, server_default="15000")
    # Temporary stops by staff (FR-30); orders already taken are not affected.
    orders_paused: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    delivery_paused: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Kitchen load (FR-37): orders in work from which the level is «moderate» / «busy», and
    # the minutes each level adds to the waiting time.
    load_moderate_from: Mapped[int] = mapped_column(SmallInteger, default=4, server_default="4")
    load_busy_from: Mapped[int] = mapped_column(SmallInteger, default=8, server_default="8")
    load_moderate_extra: Mapped[int] = mapped_column(SmallInteger, default=10, server_default="10")
    load_busy_extra: Mapped[int] = mapped_column(SmallInteger, default=20, server_default="20")
    # A level set by hand; until the moment (None with a level = until cancelled).
    kitchen_override: Mapped[str | None] = mapped_column(String(16))
    kitchen_override_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Media keys of the cafe photos, in display order (story 2.7).
    photo_keys: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    opening_hours: Mapped[list[OpeningHours]] = relationship(
        order_by="OpeningHours.weekday", lazy="selectin", cascade="all, delete-orphan"
    )


class OpeningHours(Base):
    """One interval per weekday; a weekday without a row is a day off."""

    __tablename__ = "locations_opening_hours"
    __table_args__ = (
        UniqueConstraint("location_id", "weekday"),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations_locations.id", ondelete="CASCADE")
    )
    # 0 = Monday … 6 = Sunday, as datetime.weekday().
    weekday: Mapped[int] = mapped_column(SmallInteger)
    opens_at: Mapped[time] = mapped_column(Time)
    # closes_at <= opens_at: the interval ends after midnight; equal means 24 hours.
    closes_at: Mapped[time] = mapped_column(Time)
