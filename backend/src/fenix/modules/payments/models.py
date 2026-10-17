import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from fenix.platform.db import Base


class Payment(Base):
    """One payment attempt for an order (AD-9). The order's payment status is a projection
    of these rows; `ordering` never writes it."""

    __tablename__ = "payments_payments"
    # Idempotency key: the order and the attempt number.
    __table_args__ = (UniqueConstraint("order_id", "attempt"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ordering_orders.id", ondelete="RESTRICT"), index=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations_locations.id", ondelete="RESTRICT")
    )
    attempt: Mapped[int] = mapped_column(SmallInteger)
    # online (through the provider), cash or card (marked by staff at the counter).
    method: Mapped[str] = mapped_column(String(16))
    # pending, paid, failed, cancelled, refunded.
    status: Mapped[str] = mapped_column(String(16), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str | None] = mapped_column(String(32))
    provider_payment_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("identity_users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
