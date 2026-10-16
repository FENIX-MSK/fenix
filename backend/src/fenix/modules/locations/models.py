import uuid
from datetime import datetime, time
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
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
