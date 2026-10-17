import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
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


class Order(Base):
    """An order; its status changes only through `ordering.api.transition` (AD-3)."""

    __tablename__ = "ordering_orders"
    __table_args__ = (UniqueConstraint("location_id", "business_date", "number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations_locations.id", ondelete="RESTRICT"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("identity_users.id", ondelete="RESTRICT"), index=True
    )
    # Short number for people (#047), restarted every business day of the location.
    number: Mapped[int] = mapped_column(SmallInteger)
    business_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), index=True)
    # Optimistic lock: every transition bumps it; a stale expected version is a conflict.
    version: Mapped[int] = mapped_column(Integer, default=1)
    fulfilment: Mapped[str] = mapped_column(String(16), default="pickup")
    payment_method: Mapped[str] = mapped_column(String(16))
    comment: Mapped[str] = mapped_column(Text, default="")
    customer_name: Mapped[str] = mapped_column(String(256))
    customer_phone: Mapped[str] = mapped_column(String(32))
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # Kopecks, frozen at creation (AD-6); includes the delivery fee.
    total: Mapped[int] = mapped_column(Integer)
    delivery_fee: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Delivery inside the complex (FR-7): {"house", "apartment", "entrance", "floor", "comment"}.
    address: Mapped[dict[str, str] | None] = mapped_column(JSONB)
    # Cash on delivery: the note the courier brings change for, kopecks.
    change_from: Mapped[int | None] = mapped_column(Integer)
    # Preorder (FR-8): the slot the order must be ready by; goes to the kitchen in advance.
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Internal: guests never see the reason (FR-22).
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list[OrderItem]] = relationship(
        order_by="OrderItem.position", cascade="all, delete-orphan", lazy="selectin"
    )
    events: Mapped[list[OrderEvent]] = relationship(
        order_by="OrderEvent.created_at", cascade="all, delete-orphan", lazy="selectin"
    )


class OrderItem(Base):
    """A snapshot: names and prices as they were when the order was placed (AD-6)."""

    __tablename__ = "ordering_order_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ordering_orders.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(SmallInteger)
    dish_id: Mapped[uuid.UUID]
    size_id: Mapped[uuid.UUID]
    modifier_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    title: Mapped[str] = mapped_column(String(512))
    modifier_names: Mapped[list[str]] = mapped_column(JSONB, default=list)
    quantity: Mapped[int] = mapped_column(SmallInteger)
    unit_price: Mapped[int] = mapped_column(Integer)
    total_price: Mapped[int] = mapped_column(Integer)


class OrderEvent(Base):
    """The order log (FR-25): who did what and when."""

    __tablename__ = "ordering_order_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ordering_orders.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(32))
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    actor_kind: Mapped[str] = mapped_column(String(16))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("identity_users.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderCounter(Base):
    """Last number given out per location and business day; incremented under a row lock."""

    __tablename__ = "ordering_order_counters"

    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations_locations.id", ondelete="CASCADE"), primary_key=True
    )
    business_date: Mapped[date] = mapped_column(Date, primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer)
