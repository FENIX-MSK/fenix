"""carts

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-17 00:57:31.969758
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ordering_carts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations_locations.id"],
            name=op.f("fk_ordering_carts_location_id_locations_locations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name=op.f("fk_ordering_carts_user_id_identity_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ordering_carts")),
        sa.UniqueConstraint(
            "user_id", "location_id", name=op.f("uq_ordering_carts_user_id_location_id")
        ),
    )
    op.create_table(
        "ordering_cart_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cart_id", sa.Uuid(), nullable=False),
        sa.Column("dish_id", sa.Uuid(), nullable=False),
        sa.Column("size_id", sa.Uuid(), nullable=False),
        sa.Column("modifier_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("quantity", sa.SmallInteger(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity BETWEEN 1 AND 99", name=op.f("ck_ordering_cart_items_quantity_range")
        ),
        sa.ForeignKeyConstraint(
            ["cart_id"],
            ["ordering_carts.id"],
            name=op.f("fk_ordering_cart_items_cart_id_ordering_carts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ordering_cart_items")),
    )
    op.create_index(
        op.f("ix_ordering_cart_items_cart_id"), "ordering_cart_items", ["cart_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ordering_cart_items_cart_id"), table_name="ordering_cart_items")
    op.drop_table("ordering_cart_items")
    op.drop_table("ordering_carts")
