"""Dish photos (FR-27): shrinking lives in fenix.platform.images, shared with the cafe."""

import uuid

from fenix.modules.catalog.editor import CatalogEditError
from fenix.platform.images import MAX_UPLOAD_BYTES, ImageRejectedError
from fenix.platform.images import shrink as shrink_image

__all__ = ["MAX_UPLOAD_BYTES", "new_key", "shrink"]


def shrink(data: bytes) -> bytes:
    try:
        return shrink_image(data)
    except ImageRejectedError as exc:
        raise CatalogEditError(exc.code) from exc


def new_key(dish_id: uuid.UUID) -> str:
    # Never reused: a new photo is a new key, so CDN and browser caches stay correct.
    return f"dishes/{dish_id}/{uuid.uuid7()}.webp"
