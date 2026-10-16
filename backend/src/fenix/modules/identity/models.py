import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from fenix.platform.db import Base


class IdentityUser(Base):
    __tablename__ = "identity_users"
    __table_args__ = (UniqueConstraint("platform", "external_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    platform: Mapped[str] = mapped_column(String(16))
    # A string, not a number: MAX ids are not guaranteed to be numeric.
    external_id: Mapped[str] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(256))
    last_name: Mapped[str | None] = mapped_column(String(256))
    username: Mapped[str | None] = mapped_column(String(256))
    # Where the guest came from on the very first launch; never overwritten.
    source: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
