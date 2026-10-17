"""orders

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-17 01:07:20.433845
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ordering_order_counters",
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations_locations.id"],
            name=op.f("fk_ordering_order_counters_location_id_locations_locations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "location_id", "business_date", name=op.f("pk_ordering_order_counters")
        ),
    )
    op.create_table(
        "ordering_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.SmallInteger(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("fulfilment", sa.String(length=16), nullable=False),
        sa.Column("payment_method", sa.String(length=16), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("customer_name", sa.String(length=256), nullable=False),
        sa.Column("customer_phone", sa.String(length=32), nullable=False),
        sa.Column("phone_verified", sa.Boolean(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations_locations.id"],
            name=op.f("fk_ordering_orders_location_id_locations_locations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity_users.id"],
            name=op.f("fk_ordering_orders_user_id_identity_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ordering_orders")),
        sa.UniqueConstraint(
            "location_id",
            "business_date",
            "number",
            name=op.f("uq_ordering_orders_location_id_business_date_number"),
        ),
    )
    op.create_index(
        op.f("ix_ordering_orders_location_id"), "ordering_orders", ["location_id"], unique=False
    )
    op.create_index(op.f("ix_ordering_orders_status"), "ordering_orders", ["status"], unique=False)
    op.create_index(
        op.f("ix_ordering_orders_user_id"), "ordering_orders", ["user_id"], unique=False
    )
    op.create_table(
        "ordering_order_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("actor_kind", sa.String(length=16), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["identity_users.id"],
            name=op.f("fk_ordering_order_events_actor_user_id_identity_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["ordering_orders.id"],
            name=op.f("fk_ordering_order_events_order_id_ordering_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ordering_order_events")),
    )
    op.create_index(
        op.f("ix_ordering_order_events_order_id"),
        "ordering_order_events",
        ["order_id"],
        unique=False,
    )
    op.create_table(
        "ordering_order_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("dish_id", sa.Uuid(), nullable=False),
        sa.Column("size_id", sa.Uuid(), nullable=False),
        sa.Column("modifier_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("modifier_names", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("quantity", sa.SmallInteger(), nullable=False),
        sa.Column("unit_price", sa.Integer(), nullable=False),
        sa.Column("total_price", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["ordering_orders.id"],
            name=op.f("fk_ordering_order_items_order_id_ordering_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ordering_order_items")),
    )
    op.create_index(
        op.f("ix_ordering_order_items_order_id"), "ordering_order_items", ["order_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ordering_order_items_order_id"), table_name="ordering_order_items")
    op.drop_table("ordering_order_items")
    op.drop_index(op.f("ix_ordering_order_events_order_id"), table_name="ordering_order_events")
    op.drop_table("ordering_order_events")
    op.drop_index(op.f("ix_ordering_orders_user_id"), table_name="ordering_orders")
    op.drop_index(op.f("ix_ordering_orders_status"), table_name="ordering_orders")
    op.drop_index(op.f("ix_ordering_orders_location_id"), table_name="ordering_orders")
    op.drop_table("ordering_orders")
    op.drop_table("ordering_order_counters")
