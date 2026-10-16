import io
import os
from collections.abc import Iterator
from typing import Any

import pillow_heif
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.main import create_app
from fenix.modules.catalog.editor import CatalogEditError
from fenix.modules.catalog.photos import MAX_SIDE, TARGET_BYTES, shrink
from fenix.platform.config import Settings


def encoded(fmt: str, size: tuple[int, int], mode: str = "RGB", **save: Any) -> bytes:
    # Noise compresses badly: a realistic worst case for the size target.
    image = Image.frombytes(mode, size, os.urandom(size[0] * size[1] * len(mode)))
    buffer = io.BytesIO()
    if fmt == "HEIF":
        pillow_heif.from_pillow(image).save(buffer, quality=90)
    else:
        image.save(buffer, fmt, **save)
    return buffer.getvalue()


def opened(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


@pytest.mark.parametrize(
    ("fmt", "mode"), [("JPEG", "RGB"), ("PNG", "RGBA"), ("WEBP", "RGB"), ("HEIF", "RGB")]
)
def test_phone_photo_becomes_small_webp(fmt: str, mode: str) -> None:
    # Uncompressible noise: an RGBA PNG this size is ~12 MB, still under the 15 MB limit.
    width, height = (2000, 1500) if fmt == "PNG" else (3000, 2000)
    result = shrink(
        encoded(fmt, (width, height), mode, **({"quality": 95} if fmt == "JPEG" else {}))
    )
    image = opened(result)
    assert image.format == "WEBP"
    assert image.size == (MAX_SIDE, round(MAX_SIDE * height / width))
    assert len(result) <= TARGET_BYTES * 1.5


def test_small_photo_is_not_enlarged() -> None:
    assert opened(shrink(encoded("PNG", (400, 300)))).size == (400, 300)


def test_exif_rotation_is_applied_and_metadata_dropped() -> None:
    image = Image.new("RGB", (400, 200), "red")
    exif = image.getexif()
    exif[0x0112] = 6  # rotate 90° clockwise when displayed
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", exif=exif)
    result = opened(shrink(buffer.getvalue()))
    assert result.size == (200, 400)
    assert not result.getexif()


@pytest.mark.parametrize(
    "data",
    [b"not an image", encoded("GIF", (50, 50), "L"), encoded("BMP", (50, 50))],
    ids=["garbage", "gif", "bmp"],
)
def test_unsupported(data: bytes) -> None:
    with pytest.raises(CatalogEditError) as error:
        shrink(data)
    assert error.value.code == "unsupported_image"


def test_too_large() -> None:
    with pytest.raises(CatalogEditError) as error:
        shrink(b"\xff" * (15 * 1024 * 1024 + 1))
    assert error.value.code == "image_too_large"


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    async def put(self, key: str, body: bytes, content_type: str) -> None:
        self.objects[key] = (body, content_type)


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def client(seeded: async_sessionmaker[AsyncSession], storage: FakeStorage) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        client.app.state.media_storage = storage  # type: ignore[attr-defined]
        yield client


def dish(client: TestClient, headers: dict[str, str], name: str) -> dict[str, Any]:
    catalog = client.get("/api/v1/staff/catalog", headers=headers).json()["categories"]
    found: dict[str, Any] = next(d for c in catalog for d in c["dishes"] if d["name"] == name)
    return found


def test_upload_attaches_photo_for_guests(
    client: TestClient,
    staff_headers: dict[str, str],
    auth_headers: dict[str, str],
    storage: FakeStorage,
) -> None:
    philadelphia = dish(client, staff_headers, "Филадельфия")
    response = client.post(
        f"/api/v1/staff/dishes/{philadelphia['id']}/photo",
        headers=staff_headers,
        files={"file": ("photo.jpg", encoded("JPEG", (2000, 1500)), "image/jpeg")},
    )
    assert response.status_code == 200
    url = response.json()["photo_url"]
    [key] = storage.objects
    assert url == f"/media/{key}"
    assert key.startswith(f"dishes/{philadelphia['id']}/") and key.endswith(".webp")
    assert storage.objects[key][1] == "image/webp"

    menu = client.get("/api/v1/menu", headers=auth_headers).json()
    assert (
        next(d for c in menu["categories"] for d in c["dishes"] if d["name"] == "Филадельфия")[
            "photo_url"
        ]
        == url
    )
    card = client.get(f"/api/v1/menu/dishes/{philadelphia['id']}", headers=auth_headers).json()
    assert card["photo_url"] == url

    second = client.post(
        f"/api/v1/staff/dishes/{philadelphia['id']}/photo",
        headers=staff_headers,
        files={"file": ("photo.png", encoded("PNG", (300, 300)), "image/png")},
    )
    assert second.json()["photo_url"] != url  # a new photo gets a new key

    assert (
        client.delete(
            f"/api/v1/staff/dishes/{philadelphia['id']}/photo", headers=staff_headers
        ).status_code
        == 200
    )
    assert dish(client, staff_headers, "Филадельфия")["photo_url"] is None


def test_rejected_upload_keeps_the_old_photo(
    client: TestClient, staff_headers: dict[str, str], storage: FakeStorage
) -> None:
    cola = dish(client, staff_headers, "Кола")
    path = f"/api/v1/staff/dishes/{cola['id']}/photo"
    client.post(
        path,
        headers=staff_headers,
        files={"file": ("a.png", encoded("PNG", (100, 100)), "image/png")},
    )
    before = dish(client, staff_headers, "Кола")["photo_url"]
    response = client.post(
        path, headers=staff_headers, files={"file": ("a.txt", b"hello", "text/plain")}
    )
    assert (response.status_code, response.json()["error"]["code"]) == (422, "unsupported_image")
    assert dish(client, staff_headers, "Кола")["photo_url"] == before
    assert len(storage.objects) == 1


def test_guest_cannot_upload(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    cola = dish(client, staff_headers, "Кола")
    response = client.post(
        f"/api/v1/staff/dishes/{cola['id']}/photo",
        headers=auth_headers,
        files={"file": ("a.png", encoded("PNG", (10, 10)), "image/png")},
    )
    assert response.status_code == 403
