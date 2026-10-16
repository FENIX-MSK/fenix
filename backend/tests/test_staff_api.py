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


async def add_colleague(
    seeded: async_sessionmaker[AsyncSession], telegram_id: int, name: str
) -> dict[str, str]:
    from init_data import sign_init_data

    from fenix.modules.identity import api as identity
    from fenix.modules.identity import staff
    from fenix.modules.locations import api as locations

    async with seeded() as session, session.begin():
        user = await identity.ensure_user(
            session,
            platform=identity.Platform.TELEGRAM,
            external_id=str(telegram_id),
            first_name=name,
        )
        location_id = await locations.get_default_location_id(session)
        assert location_id is not None
        await staff.add_member(session, user.id, location_id)
    return {"Authorization": f"tma {sign_init_data({'id': telegram_id, 'first_name': name})}"}


async def test_list_and_disable(
    client: TestClient, seeded: async_sessionmaker[AsyncSession], staff_headers: dict[str, str]
) -> None:
    colleague = await add_colleague(seeded, 888, "Олег")
    members = client.get("/api/v1/staff/members", headers=staff_headers).json()
    assert [(m["first_name"], m["is_me"]) for m in members] == [("Света", True), ("Олег", False)]
    oleg = members[1]["user_id"]

    assert (
        client.post(f"/api/v1/staff/members/{oleg}/disable", headers=staff_headers).status_code
        == 200
    )
    assert client.get("/api/v1/staff/me", headers=colleague).status_code == 403
    assert client.get("/api/v1/me", headers=colleague).json()["is_staff"] is False
    assert [
        m["first_name"] for m in client.get("/api/v1/staff/members", headers=staff_headers).json()
    ] == ["Света"]

    again = client.post(f"/api/v1/staff/members/{oleg}/disable", headers=staff_headers)
    assert (again.status_code, again.json()["error"]["code"]) == (404, "staff_member_not_found")


def test_last_member_cannot_be_disabled(client: TestClient, staff_headers: dict[str, str]) -> None:
    [me] = client.get("/api/v1/staff/members", headers=staff_headers).json()
    response = client.post(f"/api/v1/staff/members/{me['user_id']}/disable", headers=staff_headers)
    assert (response.status_code, response.json()["error"]["code"]) == (409, "last_staff_member")


async def test_can_disable_oneself_when_not_last(
    client: TestClient, seeded: async_sessionmaker[AsyncSession], staff_headers: dict[str, str]
) -> None:
    await add_colleague(seeded, 888, "Олег")
    me = client.get("/api/v1/staff/members", headers=staff_headers).json()[0]
    assert (
        client.post(
            f"/api/v1/staff/members/{me['user_id']}/disable", headers=staff_headers
        ).status_code
        == 200
    )
    assert client.get("/api/v1/staff/me", headers=staff_headers).status_code == 403
