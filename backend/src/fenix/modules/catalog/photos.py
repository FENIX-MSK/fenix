"""Dish photos: shrink what a phone camera produces to what a menu needs (FR-27, AD-12)."""

import io
import uuid

import pillow_heif
from PIL import Image, ImageOps, UnidentifiedImageError

from fenix.modules.catalog.editor import CatalogEditError

pillow_heif.register_heif_opener()

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_SIDE = 1280
TARGET_BYTES = 300 * 1024
ACCEPTED_FORMATS = {"JPEG", "MPO", "PNG", "WEBP", "HEIF"}
# A decompression bomb would otherwise allocate gigabytes before we can shrink it.
Image.MAX_IMAGE_PIXELS = 60_000_000


def shrink(data: bytes) -> bytes:
    """WebP, at most MAX_SIDE px on the longer side and about TARGET_BYTES."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise CatalogEditError("image_too_large")
    try:
        opened = Image.open(io.BytesIO(data))
        if opened.format not in ACCEPTED_FORMATS:
            raise CatalogEditError("unsupported_image")
        opened.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise CatalogEditError("unsupported_image") from exc

    # Phones store rotation in EXIF; apply it, then drop the metadata (location, device).
    image: Image.Image = ImageOps.exif_transpose(opened)
    image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)

    output = _encode(image)
    if len(output) > TARGET_BYTES and image.mode == "RGBA":
        # Transparency that will not compress (noise, gradients): flatten onto white,
        # the photo stays within the size target and looks the same on a card.
        flat = Image.new("RGB", image.size, "white")
        flat.paste(image, mask=image.getchannel("A"))
        output = _encode(flat)
    return output


def _encode(image: Image.Image) -> bytes:
    output = b""
    for quality in (82, 74, 66, 58, 50):
        buffer = io.BytesIO()
        # alpha_quality: the alpha channel is otherwise lossless and ignores `quality`.
        image.save(buffer, "WEBP", quality=quality, alpha_quality=quality, method=4)
        output = buffer.getvalue()
        if len(output) <= TARGET_BYTES:
            break
    return output


def new_key(dish_id: uuid.UUID) -> str:
    # Never reused: a new photo is a new key, so CDN and browser caches stay correct.
    return f"dishes/{dish_id}/{uuid.uuid7()}.webp"
