import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fenix.platform.db import Base


class Cart(Base):
    """A guest's cart at a location. Holds the choice only: prices are computed on read (AD-6)."""

    __tablename__ = "ordering_carts"
    __table_args__ = (UniqueConstraint("user_id", "location_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity_users.id", ondelete="CASCADE"))
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations_locations.id", ondelete="CASCADE")
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list[CartItem]] = relationship(
        order_by="CartItem.created_at", cascade="all, delete-orphan", lazy="selectin"
    )


class CartItem(Base):
    __tablename__ = "ordering_cart_items"
    __table_args__ = (CheckConstraint("quantity BETWEEN 1 AND 99", name="quantity_range"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    cart_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ordering_carts.id", ondelete="CASCADE"), index=True
    )
    # Ids, not foreign keys: a line outlives a dish removed from the menu and shows as
    # unavailable instead of disappearing silently.
    dish_id: Mapped[uuid.UUID]
    size_id: Mapped[uuid.UUID]
    # Sorted, so the same choice made twice is the same line.
    modifier_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    quantity: Mapped[int] = mapped_column(SmallInteger)
    # Names at the moment of adding, shown if the dish is later deleted.
    title: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
