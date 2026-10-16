import io
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.main import create_app
from fenix.platform.config import Settings

ALL_WEEK = [{"weekday": d, "opens_at": "9:00", "closes_at": "22:00"} for d in range(7)]
BODY: dict[str, Any] = {
    "address": "Москва, ул. Новая, 1",
    "latitude": 55.75,
    "longitude": 37.61,
    "phone": "+7 (999) 123-45-67",
    "description": "Новое описание",
    "social_links": [
        {"kind": "telegram", "title": "Telegram", "url": "https://t.me/phoenix_catering"}
    ],
    "opening_hours": ALL_WEEK,
}


class Storage:
    def __init__(self) -> None:
        self.keys: list[str] = []

    async def put(self, key: str, body: bytes, content_type: str) -> None:
        self.keys.append(key)


@pytest.fixture
def client(seeded: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        client.app.state.media_storage = Storage()  # type: ignore[attr-defined]
        yield client


def guest(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    body: dict[str, Any] = client.get("/api/v1/location", headers=headers).json()
    return body


def put(client: TestClient, headers: dict[str, str], body: dict[str, Any]) -> Any:
    return client.put("/api/v1/staff/location", headers=headers, json=body)


def test_changes_are_visible_to_guests(
    client: TestClient, staff_headers: dict[str, str], auth_headers: dict[str, str]
) -> None:
    assert put(client, staff_headers, BODY).status_code == 200
    info = guest(client, auth_headers)
    assert (info["address"], info["phone"], info["description"]) == (
        "Москва, ул. Новая, 1",
        "+7 (999) 123-45-67",
        "Новое описание",
    )
    assert info["map_url"] == "https://yandex.ru/maps/?pt=37.61,55.75&z=17&l=map"
    assert [link["title"] for link in info["social_links"]] == ["Telegram"]


def test_day_off_and_after_midnight(
    client: TestClient, staff_headers: dict[str, str], auth_headers: dict[str, str]
) -> None:
    hours = [{"weekday": d, "opens_at": "18:00", "closes_at": "2:00"} for d in range(6)]
    assert put(client, staff_headers, BODY | {"opening_hours": hours}).status_code == 200
    info = guest(client, auth_headers)
    assert [h["weekday"] for h in info["opening_hours"]] == [0, 1, 2, 3, 4, 5]
    assert info["opening_hours"][0] == {"weekday": 0, "opens_at": "18:00", "closes_at": "2:00"}


def test_status_follows_new_hours_at_once(
    client: TestClient, staff_headers: dict[str, str], auth_headers: dict[str, str]
) -> None:
    always = [{"weekday": d, "opens_at": "0:00", "closes_at": "0:00"} for d in range(7)]
    put(client, staff_headers, BODY | {"opening_hours": always})
    assert guest(client, auth_headers)["status"]["text"] == "Открыто круглосуточно"
    put(client, staff_headers, BODY | {"opening_hours": []})
    assert guest(client, auth_headers)["status"]["text"] == "Закрыто"


@pytest.mark.parametrize(
    ("patch", "code"),
    [
        ({"opening_hours": [{"weekday": 0, "opens_at": "25:00", "closes_at": "2:00"}]}, "bad_time"),
        ({"opening_hours": [ALL_WEEK[0], ALL_WEEK[0]]}, "bad_weekday"),
        ({"phone": " "}, "contacts_required"),
        ({"latitude": 55.0, "longitude": None}, "bad_coordinates"),
        ({"social_links": [{"title": "Сайт", "url": "javascript:alert(1)"}]}, "bad_social_link"),
    ],
)
def test_validation(
    client: TestClient, staff_headers: dict[str, str], patch: dict[str, Any], code: str
) -> None:
    response = put(client, staff_headers, BODY | patch)
    assert (response.status_code, response.json()["error"]["code"]) == (422, code)


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (800, 600), "orange").save(buffer, "PNG")
    return buffer.getvalue()


def test_cafe_photos(
    client: TestClient, staff_headers: dict[str, str], auth_headers: dict[str, str]
) -> None:
    upload = client.post(
        "/api/v1/staff/location/photos",
        headers=staff_headers,
        files={"file": ("a.png", png(), "image/png")},
    )
    assert upload.status_code == 200
    [url] = upload.json()["photos"]
    assert url.startswith("/media/cafe/") and url.endswith(".webp")
    assert guest(client, auth_headers)["photos"] == [url]

    removed = client.delete(
        "/api/v1/staff/location/photos", headers=staff_headers, params={"key": url}
    )
    assert removed.json() == {"photos": []}
    assert guest(client, auth_headers)["photos"] == []


def test_bad_photo(client: TestClient, staff_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/staff/location/photos",
        headers=staff_headers,
        files={"file": ("a.txt", b"x", "text/plain")},
    )
    assert (response.status_code, response.json()["error"]["code"]) == (422, "unsupported_image")


def test_guest_cannot_edit(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert put(client, auth_headers, BODY).status_code == 403
