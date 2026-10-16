"""catalog

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-16 22:46:45.114562
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "catalog_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_hidden", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_categories")),
    )
    op.create_table(
        "catalog_modifier_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("min_choice", sa.SmallInteger(), nullable=False),
        sa.Column("max_choice", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "min_choice >= 0 AND max_choice >= min_choice AND max_choice >= 1",
            name=op.f("ck_catalog_modifier_groups_choice_bounds"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_modifier_groups")),
    )
    op.create_table(
        "catalog_category_modifier_groups",
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["catalog_categories.id"],
            name=op.f("fk_catalog_category_modifier_groups_category_id_catalog_categories"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["catalog_modifier_groups.id"],
            name=op.f("fk_catalog_category_modifier_groups_group_id_catalog_modifier_groups"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "category_id", "group_id", name=op.f("pk_catalog_category_modifier_groups")
        ),
    )
    op.create_table(
        "catalog_dishes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("portion", sa.String(length=32), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_hidden", sa.Boolean(), nullable=False),
        sa.Column("photo_key", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["catalog_categories.id"],
            name=op.f("fk_catalog_dishes_category_id_catalog_categories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_dishes")),
    )
    op.create_index(
        op.f("ix_catalog_dishes_category_id"), "catalog_dishes", ["category_id"], unique=False
    )
    op.create_table(
        "catalog_modifiers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("price_delta", sa.Integer(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint(
            "price_delta >= 0", name=op.f("ck_catalog_modifiers_price_delta_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["catalog_modifier_groups.id"],
            name=op.f("fk_catalog_modifiers_group_id_catalog_modifier_groups"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_modifiers")),
    )
    op.create_index(
        op.f("ix_catalog_modifiers_group_id"), "catalog_modifiers", ["group_id"], unique=False
    )
    op.create_table(
        "catalog_dish_modifier_groups",
        sa.Column("dish_id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dish_id"],
            ["catalog_dishes.id"],
            name=op.f("fk_catalog_dish_modifier_groups_dish_id_catalog_dishes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["catalog_modifier_groups.id"],
            name=op.f("fk_catalog_dish_modifier_groups_group_id_catalog_modifier_groups"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "dish_id", "group_id", name=op.f("pk_catalog_dish_modifier_groups")
        ),
    )
    op.create_table(
        "catalog_dish_sizes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dish_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("portion", sa.String(length=32), nullable=True),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("price >= 0", name=op.f("ck_catalog_dish_sizes_price_non_negative")),
        sa.ForeignKeyConstraint(
            ["dish_id"],
            ["catalog_dishes.id"],
            name=op.f("fk_catalog_dish_sizes_dish_id_catalog_dishes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_dish_sizes")),
    )
    op.create_index(
        op.f("ix_catalog_dish_sizes_dish_id"), "catalog_dish_sizes", ["dish_id"], unique=False
    )
    op.create_table(
        "catalog_stop_list",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("dish_size_id", sa.Uuid(), nullable=True),
        sa.Column("modifier_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(dish_size_id IS NULL) <> (modifier_id IS NULL)",
            name=op.f("ck_catalog_stop_list_size_xor_modifier"),
        ),
        sa.ForeignKeyConstraint(
            ["dish_size_id"],
            ["catalog_dish_sizes.id"],
            name=op.f("fk_catalog_stop_list_dish_size_id_catalog_dish_sizes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations_locations.id"],
            name=op.f("fk_catalog_stop_list_location_id_locations_locations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["modifier_id"],
            ["catalog_modifiers.id"],
            name=op.f("fk_catalog_stop_list_modifier_id_catalog_modifiers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_stop_list")),
    )
    op.create_index(
        "uq_catalog_stop_list_location_id_dish_size_id",
        "catalog_stop_list",
        ["location_id", "dish_size_id"],
        unique=True,
        postgresql_where=sa.text("dish_size_id IS NOT NULL"),
    )
    op.create_index(
        "uq_catalog_stop_list_location_id_modifier_id",
        "catalog_stop_list",
        ["location_id", "modifier_id"],
        unique=True,
        postgresql_where=sa.text("modifier_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_catalog_stop_list_location_id_modifier_id",
        table_name="catalog_stop_list",
        postgresql_where=sa.text("modifier_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_catalog_stop_list_location_id_dish_size_id",
        table_name="catalog_stop_list",
        postgresql_where=sa.text("dish_size_id IS NOT NULL"),
    )
    op.drop_table("catalog_stop_list")
    op.drop_index(op.f("ix_catalog_dish_sizes_dish_id"), table_name="catalog_dish_sizes")
    op.drop_table("catalog_dish_sizes")
    op.drop_table("catalog_dish_modifier_groups")
    op.drop_index(op.f("ix_catalog_modifiers_group_id"), table_name="catalog_modifiers")
    op.drop_table("catalog_modifiers")
    op.drop_index(op.f("ix_catalog_dishes_category_id"), table_name="catalog_dishes")
    op.drop_table("catalog_dishes")
    op.drop_table("catalog_category_modifier_groups")
    op.drop_table("catalog_modifier_groups")
    op.drop_table("catalog_categories")
