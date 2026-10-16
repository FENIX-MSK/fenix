from collections.abc import Iterator
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.main import create_app
from fenix.platform.config import Settings


@pytest.fixture
def client(seeded: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


def test_guest_is_forbidden(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/staff/me", headers=auth_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    assert client.get("/api/v1/me", headers=auth_headers).json()["is_staff"] is False


def test_unsigned_is_unauthorized(client: TestClient) -> None:
    assert client.get("/api/v1/staff/me").status_code == 401


def test_staff_member(client: TestClient, staff_headers: dict[str, str]) -> None:
    assert client.get("/api/v1/staff/me", headers=staff_headers).json() == {"first_name": "Света"}
    assert client.get("/api/v1/me", headers=staff_headers).json()["is_staff"] is True


def test_invitation_link(client: TestClient, staff_headers: dict[str, str]) -> None:
    body = client.post("/api/v1/staff/invitations", headers=staff_headers).json()
    url = urlparse(body["url"])
    assert (url.scheme, url.netloc, url.path) == ("https", "t.me", "/fenix_test_bot")
    [start] = parse_qs(url.query)["start"]
    assert start.startswith("inv_") and len(start) <= 64
    assert body["expires_at"]


def test_guest_cannot_invite(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.post("/api/v1/staff/invitations", headers=auth_headers).status_code == 403
