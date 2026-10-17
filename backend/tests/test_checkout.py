from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from init_data import sign_contact
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.main import create_app
from fenix.modules.identity.models import IdentityUser
from fenix.platform.config import Settings


@pytest.fixture
def client(seeded: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


def contact(client: TestClient, headers: dict[str, str], **body: Any) -> Any:
    return client.post("/api/v1/me/contact", headers=headers, json=body)


def test_first_checkout_asks_for_phone_and_consent(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    always = [{"weekday": d, "opens_at": "0:00", "closes_at": "0:00"} for d in range(7)]
    location = client.get("/api/v1/location", headers=auth_headers).json()
    client.put(
        "/api/v1/staff/location",
        headers=staff_headers,
        json={"address": location["address"], "phone": location["phone"], "opening_hours": always},
    )
    body = client.get("/api/v1/checkout", headers=auth_headers).json()
    assert body["is_open"] is True
    assert body["asap_minutes"] == 20
    assert body["fulfilment"] == ["pickup", "delivery"]
    assert body["contact"] == {"first_name": "Аня", "phone": None, "has_consent": False}


def test_closed_location(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    location = client.get("/api/v1/location", headers=auth_headers).json()
    client.put(
        "/api/v1/staff/location",
        headers=staff_headers,
        json={"address": location["address"], "phone": location["phone"], "opening_hours": []},
    )
    body = client.get("/api/v1/checkout", headers=auth_headers).json()
    assert (body["is_open"], body["status_text"]) == (False, "Закрыто")


async def test_shared_contact_is_verified(
    client: TestClient, auth_headers: dict[str, str], seeded: async_sessionmaker[AsyncSession]
) -> None:
    response = contact(
        client, auth_headers, contact_raw=sign_contact(42, "79991234567"), consent=True
    )
    assert response.json() == {"first_name": "Аня", "phone": "+79991234567", "has_consent": True}
    async with seeded() as session:
        user = (
            await session.execute(select(IdentityUser).where(IdentityUser.external_id == "42"))
        ).scalar_one()
    assert user.phone_verified is True
    assert user.privacy_consent_at is not None
    first_consent = user.privacy_consent_at

    contact(client, auth_headers, consent=True, first_name="Анна")
    async with seeded() as session:
        user = (
            await session.execute(select(IdentityUser).where(IdentityUser.external_id == "42"))
        ).scalar_one()
    assert (user.privacy_consent_at, user.first_name) == (first_consent, "Анна")


def test_contact_of_another_user_is_rejected(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = contact(client, auth_headers, contact_raw=sign_contact(7, "79991234567"))
    assert (response.status_code, response.json()["error"]["code"]) == (422, "bad_contact")


def test_forged_contact_is_rejected(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = contact(
        client, auth_headers, contact_raw=sign_contact(42, "79991234567", token="1:other")
    )
    assert response.json()["error"]["code"] == "bad_contact"


@pytest.mark.parametrize(
    ("typed", "stored"),
    [
        ("8 (999) 123-45-67", "+79991234567"),
        ("9991234567", "+79991234567"),
        ("+44 20 7946 0958", "+442079460958"),
    ],
)
def test_typed_phone_is_normalized(
    client: TestClient, auth_headers: dict[str, str], typed: str, stored: str
) -> None:
    assert contact(client, auth_headers, phone=typed).json()["phone"] == stored


def test_bad_phone(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = contact(client, auth_headers, phone="12345")
    assert (response.status_code, response.json()["error"]["code"]) == (422, "bad_phone")
