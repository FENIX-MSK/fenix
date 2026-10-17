import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from fenix.platform.db import Base


class StaffChat(Base):
    """The group chat of a location's staff (FR-24): one per location."""

    __tablename__ = "notifications_staff_chats"

    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations_locations.id", ondelete="CASCADE"), primary_key=True
    )
    platform: Mapped[str] = mapped_column(String(16))
    chat_id: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(256), default="")
    bound_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("identity_users.id", ondelete="SET NULL")
    )
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlertChat(Base):
    """The chat that receives monitoring alerts (NFR-6): one for the whole system."""

    __tablename__ = "notifications_alert_chats"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    platform: Mapped[str] = mapped_column(String(16))
    chat_id: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(256), default="")
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
