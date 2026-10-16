"""identity users

Revision ID: 0001
Revises:
Create Date: 2026-10-16 17:45:59.452388
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "identity_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("first_name", sa.String(length=256), nullable=False),
        sa.Column("last_name", sa.String(length=256), nullable=True),
        sa.Column("username", sa.String(length=256), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_identity_users")),
        sa.UniqueConstraint(
            "platform", "external_id", name=op.f("uq_identity_users_platform_external_id")
        ),
    )


def downgrade() -> None:
    op.drop_table("identity_users")
