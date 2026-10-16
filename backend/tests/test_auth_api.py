from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from init_data import sign_init_data
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.http.deps import get_session
from fenix.main import create_app
from fenix.modules.identity.models import IdentityUser
from fenix.platform.config import Settings

UNAUTHORIZED = {
    "error": {
        "code": "unauthorized",
        "message": "Valid Telegram Mini App launch data is required",
        "details": {},
    }
}


@pytest.fixture
def client(session_factory: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


def test_me_is_the_launching_user(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    init_data = sign_init_data({"id": 42, "first_name": "Аня"}, start_param="qr_table")
    response = client.get("/api/v1/me", headers={"Authorization": f"tma {init_data}"})
    assert response.status_code == 200
    assert response.json()["first_name"] == "Аня"

    again = client.get("/api/v1/me", headers={"Authorization": f"tma {init_data}"})
    assert again.json()["id"] == response.json()["id"]


async def test_user_created_by_api_keeps_start_param(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    init_data = sign_init_data({"id": 7, "first_name": "Олег"}, start_param="qr_table")
    assert client.get("/api/v1/me", headers={"Authorization": f"tma {init_data}"}).is_success
    async with session_factory() as session:
        user = (await session.execute(select(IdentityUser))).scalar_one()
    assert (user.external_id, user.source) == ("7", "qr_table")


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="no-header"),
        pytest.param({"Authorization": f"Bearer {sign_init_data()}"}, id="other-scheme"),
        pytest.param({"Authorization": "tma "}, id="empty"),
        pytest.param({"Authorization": f"tma {sign_init_data()}x"}, id="bad-signature"),
        pytest.param({"Authorization": f"tma {sign_init_data(auth_date=1)}"}, id="expired"),
    ],
)
def test_rejected_requests_get_401(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get("/api/v1/me", headers=headers)
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED


def test_failed_commit_is_not_reported_as_success(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def session_whose_commit_fails() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session
            raise RuntimeError("commit failed")

    app = create_app(Settings())
    app.dependency_overrides[get_session] = session_whose_commit_fails
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/me", headers={"Authorization": f"tma {sign_init_data()}"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
