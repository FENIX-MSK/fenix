import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    # From Telegram's «Поделиться контактом» (verified) or typed by the guest.
    phone: Mapped[str | None] = mapped_column(String(32))
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # When the guest accepted the privacy policy (FR-10); asked once.
    privacy_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Where the guest came from on the very first launch; never overwritten.
    source: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StaffMembership(Base):
    """A user working at a location (AD-7). No roles: every active member has equal rights."""

    __tablename__ = "identity_staff_memberships"
    __table_args__ = (UniqueConstraint("user_id", "location_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity_users.id", ondelete="CASCADE"))
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations_locations.id", ondelete="CASCADE"), index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[IdentityUser] = relationship()


class Invitation(Base):
    """A one-time link into the bot. Only the SHA-256 of the token is stored."""

    __tablename__ = "identity_invitations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations_locations.id", ondelete="CASCADE")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("identity_users.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("identity_users.id", ondelete="SET NULL")
    )
