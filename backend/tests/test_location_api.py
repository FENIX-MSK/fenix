from collections.abc import Iterator
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.main import create_app
from fenix.modules.locations import api as locations
from fenix.modules.locations.models import Location
from fenix.platform.config import Settings


@pytest.fixture
def client(session_factory: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


async def seed(factory: async_sessionmaker[AsyncSession]) -> None:
    async with factory() as session, session.begin():
        await locations.seed_defaults(session)


async def test_location_info(
    client: TestClient,
    session_factory: async_sessionmaker[AsyncSession],
    auth_headers: dict[str, str],
) -> None:
    await seed(session_factory)
    body = client.get("/api/v1/location", headers=auth_headers).json()
    assert body["name"] == "Феникс бистро"
    assert body["map_url"] == "https://yandex.ru/maps/?text=" + quote("Адрес уточняется")
    assert [link["kind"] for link in body["social_links"]] == ["telegram", "max"]
    assert body["social_links"][0]["url"] == "https://t.me/phoenix_catering"
    assert body["opening_hours"][0] == {"weekday": 0, "opens_at": "9:00", "closes_at": "22:00"}
    assert len(body["opening_hours"]) == 7
    status = body["status"]
    assert status["text"].startswith(("Открыто до", "Закрыто, откроемся"))
    moment = status["closes_at"] or status["opens_at"]
    assert moment.endswith("+03:00")


async def test_map_url_uses_coordinates(
    client: TestClient,
    session_factory: async_sessionmaker[AsyncSession],
    auth_headers: dict[str, str],
) -> None:
    await seed(session_factory)
    async with session_factory() as session, session.begin():
        location = (await session.execute(select(Location))).scalar_one()
        location.latitude, location.longitude = 55.75, 37.61
    body = client.get("/api/v1/location", headers=auth_headers).json()
    assert body["map_url"] == "https://yandex.ru/maps/?pt=37.61,55.75&z=17&l=map"


def test_no_location_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/location", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "location_not_found"


def test_location_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/location")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
