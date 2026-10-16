import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fenix.platform.db import Base


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class Category(Base):
    __tablename__ = "catalog_categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    name: Mapped[str] = mapped_column(String(128))
    # Shown under the title, e.g. «32 см» for pizza.
    description: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[int] = mapped_column(Integer)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = _created_at()

    dishes: Mapped[list[Dish]] = relationship(
        back_populates="category", order_by="Dish.position", cascade="all, delete-orphan"
    )
    modifier_groups: Mapped[list[CategoryModifierGroup]] = relationship(
        order_by="CategoryModifierGroup.position", cascade="all, delete-orphan"
    )


class Dish(Base):
    __tablename__ = "catalog_dishes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("catalog_categories.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(256))
    # Ingredients as printed on the menu; for sets, the rolls they contain.
    description: Mapped[str] = mapped_column(Text, default="")
    # Weight or volume as printed, e.g. "190 g" in Russian; sizes may carry their own.
    portion: Mapped[str | None] = mapped_column(String(32))
    position: Mapped[int] = mapped_column(Integer)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    photo_key: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = _created_at()

    category: Mapped[Category] = relationship(back_populates="dishes")
    sizes: Mapped[list[DishSize]] = relationship(
        back_populates="dish", order_by="DishSize.position", cascade="all, delete-orphan"
    )
    modifier_groups: Mapped[list[DishModifierGroup]] = relationship(
        order_by="DishModifierGroup.position", cascade="all, delete-orphan"
    )


class DishSize(Base):
    """A priced variant of a dish. A dish with one price has one size with an empty name."""

    __tablename__ = "catalog_dish_sizes"
    __table_args__ = (CheckConstraint("price >= 0", name="price_non_negative"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    dish_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("catalog_dishes.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(64), default="")
    # Kopecks (AD-6).
    price: Mapped[int] = mapped_column(Integer)
    portion: Mapped[str | None] = mapped_column(String(32))
    position: Mapped[int] = mapped_column(SmallInteger)

    dish: Mapped[Dish] = relationship(back_populates="sizes")


class ModifierGroup(Base):
    __tablename__ = "catalog_modifier_groups"
    __table_args__ = (
        CheckConstraint(
            "min_choice >= 0 AND max_choice >= min_choice AND max_choice >= 1", name="choice_bounds"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    name: Mapped[str] = mapped_column(String(128))
    min_choice: Mapped[int] = mapped_column(SmallInteger)
    max_choice: Mapped[int] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = _created_at()

    modifiers: Mapped[list[Modifier]] = relationship(
        back_populates="group", order_by="Modifier.position", cascade="all, delete-orphan"
    )


class Modifier(Base):
    __tablename__ = "catalog_modifiers"
    __table_args__ = (CheckConstraint("price_delta >= 0", name="price_delta_non_negative"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("catalog_modifier_groups.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    # Kopecks added to the size price; 0 for a free choice.
    price_delta: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(SmallInteger)

    group: Mapped[ModifierGroup] = relationship(back_populates="modifiers")


class DishModifierGroup(Base):
    __tablename__ = "catalog_dish_modifier_groups"

    dish_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("catalog_dishes.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("catalog_modifier_groups.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(SmallInteger)

    group: Mapped[ModifierGroup] = relationship()


class CategoryModifierGroup(Base):
    """A group offered for every dish of the category, e.g. coffee add-ons."""

    __tablename__ = "catalog_category_modifier_groups"

    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("catalog_categories.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("catalog_modifier_groups.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(SmallInteger)

    group: Mapped[ModifierGroup] = relationship()


class StopListEntry(Base):
    """A size or a modifier that ran out at a location (AD-10). Exactly one of the two is set."""

    __tablename__ = "catalog_stop_list"
    __table_args__ = (
        CheckConstraint(
            "(dish_size_id IS NULL) <> (modifier_id IS NULL)", name="size_xor_modifier"
        ),
        Index(
            "uq_catalog_stop_list_location_id_dish_size_id",
            "location_id",
            "dish_size_id",
            unique=True,
            postgresql_where=text("dish_size_id IS NOT NULL"),
        ),
        Index(
            "uq_catalog_stop_list_location_id_modifier_id",
            "location_id",
            "modifier_id",
            unique=True,
            postgresql_where=text("modifier_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations_locations.id", ondelete="CASCADE")
    )
    dish_size_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("catalog_dish_sizes.id", ondelete="CASCADE")
    )
    modifier_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("catalog_modifiers.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = _created_at()
