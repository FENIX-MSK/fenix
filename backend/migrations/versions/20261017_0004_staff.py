"""staff

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-17 00:21:38.572310
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "identity_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["identity_users.id"],
            name=op.f("fk_identity_invitations_created_by_identity_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations_locations.id"],
            name=op.f("fk_identity_invitations_location_id_locations_locations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["used_by"],
            ["identity_users.id"],
            name=op.f("fk_identity_invitations_used_by_identity_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_identity_invitations")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_identity_invitations_token_hash")),
    )
    op.create_table(
        "identity_staff_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations_locations.id"],
            name=op.f("fk_identity_staff_memberships_location_id_locations_locations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name=op.f("fk_identity_staff_memberships_user_id_identity_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_identity_staff_memberships")),
        sa.UniqueConstraint(
            "user_id", "location_id", name=op.f("uq_identity_staff_memberships_user_id_location_id")
        ),
    )
    op.create_index(
        op.f("ix_identity_staff_memberships_location_id"),
        "identity_staff_memberships",
        ["location_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_identity_staff_memberships_location_id"), table_name="identity_staff_memberships"
    )
    op.drop_table("identity_staff_memberships")
    op.drop_table("identity_invitations")
