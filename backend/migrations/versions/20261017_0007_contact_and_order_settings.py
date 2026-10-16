"""contact and order settings

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-17 01:03:34.531759
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("identity_users", sa.Column("phone", sa.String(length=32), nullable=True))
    op.add_column(
        "identity_users",
        sa.Column("phone_verified", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "identity_users", sa.Column("privacy_consent_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "locations_locations",
        sa.Column("prep_minutes", sa.SmallInteger(), server_default="20", nullable=False),
    )
    op.add_column(
        "locations_locations",
        sa.Column("unpaid_timeout_minutes", sa.SmallInteger(), server_default="15", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("locations_locations", "unpaid_timeout_minutes")
    op.drop_column("locations_locations", "prep_minutes")
    op.drop_column("identity_users", "privacy_consent_at")
    op.drop_column("identity_users", "phone_verified")
    op.drop_column("identity_users", "phone")
