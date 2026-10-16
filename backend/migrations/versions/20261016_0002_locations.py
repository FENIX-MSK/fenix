"""locations

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-16 17:54:11.912412
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "locations_locations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("address", sa.String(length=512), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("social_links", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locations_locations")),
    )
    op.create_table(
        "locations_opening_hours",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("opens_at", sa.Time(), nullable=False),
        sa.Column("closes_at", sa.Time(), nullable=False),
        sa.CheckConstraint(
            "weekday BETWEEN 0 AND 6", name=op.f("ck_locations_opening_hours_weekday_range")
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations_locations.id"],
            name=op.f("fk_locations_opening_hours_location_id_locations_locations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locations_opening_hours")),
        sa.UniqueConstraint(
            "location_id", "weekday", name=op.f("uq_locations_opening_hours_location_id_weekday")
        ),
    )


def downgrade() -> None:
    op.drop_table("locations_opening_hours")
    op.drop_table("locations_locations")
