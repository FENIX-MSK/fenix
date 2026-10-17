"""Epic 6: promotions, prices with a discount, the birthday claim and its confirmation."""

from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_orders import add_to_cart, place

from fenix.main import create_app
from fenix.modules.catalog.promotions import discounted
from fenix.platform.config import Settings


@pytest.fixture
def client(ready_guest: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


def promotions(client: TestClient, staff: dict[str, str]) -> Any:
    return client.get("/api/v1/staff/promotions", headers=staff).json()


def create(client: TestClient, staff: dict[str, str], **body: Any) -> Any:
    return client.post(
        "/api/v1/staff/promotions",
        headers=staff,
        json={"title": "Скидка", "percent": 20, **body},
    )


def dish(client: TestClient, headers: dict[str, str], name: str) -> Any:
    menu = client.get("/api/v1/menu", headers=headers).json()
    return next(d for c in menu["categories"] for d in c["dishes"] if d["name"] == name)


def test_birthday_promotion_is_seeded(client: TestClient, staff_headers: dict[str, str]) -> None:
    [birthday] = promotions(client, staff_headers)
    assert birthday["percent"] == 10
    assert birthday["kind"] == "checked"
    assert birthday["category_id"] is None and birthday["ends_on"] is None


def test_validation(client: TestClient, staff_headers: dict[str, str]) -> None:
    today = date.today()
    bad_dates = create(
        client,
        staff_headers,
        starts_on=str(today),
        ends_on=str(today - timedelta(days=1)),
    )
    assert bad_dates.json()["error"]["code"] == "bad_dates"
    assert create(client, staff_headers, percent=0).status_code == 422


def test_rounding() -> None:
    assert discounted(28000, 10) == 25200
    assert discounted(59900, 20) == 47900


def test_automatic_promotion_in_menu_cart_and_order(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    before = dish(client, auth_headers, "Филадельфия")
    created = create(client, staff_headers, percent=20)
    assert created.status_code == 200
    after = dish(client, auth_headers, "Филадельфия")
    assert after["discount_percent"] == 20
    assert after["original_price_from"] == before["price_from"]
    assert after["price_from"] == discounted(before["price_from"], 20)
    menu = client.get("/api/v1/menu", headers=auth_headers).json()
    assert {p["kind"] for p in menu["promotions"]} == {"auto", "checked"}

    add_to_cart(client, auth_headers, "Филадельфия")
    cart = client.get("/api/v1/cart", headers=auth_headers).json()
    assert cart["total"] == after["price_from"]
    assert cart["original_total"] == before["price_from"]
    order = place(client, auth_headers).json()
    assert order["total"] == cart["total"]
    assert order["lines"][0]["promotion_title"] == "Скидка"
    assert order["lines"][0]["original_unit_price"] == before["price_from"]


def test_largest_promotion_wins_and_category_scope(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    menu = client.get("/api/v1/menu", headers=auth_headers).json()
    rolls = next(c for c in menu["categories"] if c["name"] == "Роллы")
    create(client, staff_headers, percent=10)
    create(client, staff_headers, percent=30, category_id=rolls["id"], title="Роллы −30%")
    roll = dish(client, auth_headers, "Филадельфия")
    coffee = dish(client, auth_headers, "Капучино")
    assert roll["discount_percent"] == 30
    assert coffee["discount_percent"] == 10


def test_expired_and_disabled_promotions_do_not_apply(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    yesterday = str(date.today() - timedelta(days=2))
    create(client, staff_headers, starts_on=yesterday, ends_on=yesterday)
    created = create(client, staff_headers, percent=50).json()
    assert dish(client, auth_headers, "Капучино")["discount_percent"] == 50
    client.put(
        f"/api/v1/staff/promotions/{created['id']}",
        headers=staff_headers,
        json={**created, "enabled": False},
    ).raise_for_status()
    assert dish(client, auth_headers, "Капучино")["discount_percent"] == 0


def birthday_id(client: TestClient, headers: dict[str, str]) -> str:
    checkout = client.get("/api/v1/checkout", headers=headers).json()
    return checkout["checked_promotions"][0]["id"]


def test_birthday_claim_and_confirmation(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    add_to_cart(client, auth_headers, "Филадельфия")
    full = client.get("/api/v1/cart", headers=auth_headers).json()["total"]
    checkout = client.get("/api/v1/checkout", headers=auth_headers).json()
    [claim] = checkout["checked_promotions"]
    assert claim["preview_total"] == discounted(full, 10)

    online = client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={"payment_method": "online", "comment": "", "claimed_promotion_id": claim["id"]},
    )
    assert online.json()["error"]["code"] == "claim_requires_on_site"
    order = client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={"payment_method": "cash", "comment": "", "claimed_promotion_id": claim["id"]},
    ).json()
    assert order["total"] == claim["preview_total"]
    assert order["discount_status"] == "pending"

    card = client.get(f"/api/v1/staff/orders/{order['id']}", headers=staff_headers).json()
    assert card["discount_title"].startswith("В день рождения")
    assert card["total_without_claim"] == full
    current = card
    for action in ("accept", "start_cooking", "mark_ready"):
        current = client.post(
            f"/api/v1/staff/orders/{order['id']}/actions",
            headers=staff_headers,
            json={"action": action, "expected_version": current["version"]},
        ).json()
    blocked = client.post(
        f"/api/v1/staff/orders/{order['id']}/actions",
        headers=staff_headers,
        json={"action": "hand_over", "expected_version": current["version"], "paid_with": "cash"},
    )
    assert blocked.json()["error"]["code"] == "discount_decision_required"
    confirmed = client.post(
        f"/api/v1/staff/orders/{order['id']}/discount",
        headers=staff_headers,
        json={"confirm": True, "expected_version": current["version"]},
    ).json()
    assert confirmed["discount_status"] == "confirmed"
    assert confirmed["total"] == claim["preview_total"]
    assert confirmed["log"][-1]["action"] == "confirm_discount"
    handed = client.post(
        f"/api/v1/staff/orders/{order['id']}/actions",
        headers=staff_headers,
        json={"action": "hand_over", "expected_version": confirmed["version"], "paid_with": "cash"},
    ).json()
    assert handed["status"] == "handed_over"


def test_rejected_claim_restores_the_full_price(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    add_to_cart(client, auth_headers, "Капучино", 2)
    full = client.get("/api/v1/cart", headers=auth_headers).json()["total"]
    order = client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={
            "payment_method": "card",
            "comment": "",
            "claimed_promotion_id": birthday_id(client, auth_headers),
        },
    ).json()
    rejected = client.post(
        f"/api/v1/staff/orders/{order['id']}/discount",
        headers=staff_headers,
        json={"confirm": False, "expected_version": order["version"]},
    ).json()
    assert rejected["discount_status"] == "rejected"
    assert rejected["total"] == full
    assert sum(line["total_price"] for line in rejected["lines"]) == full
    again = client.post(
        f"/api/v1/staff/orders/{order['id']}/discount",
        headers=staff_headers,
        json={"confirm": True, "expected_version": rejected["version"]},
    )
    assert again.json()["error"]["code"] == "no_discount_claim"


def test_automatic_beats_smaller_claim(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    create(client, staff_headers, percent=15)
    add_to_cart(client, auth_headers, "Капучино")
    cart = client.get("/api/v1/cart", headers=auth_headers).json()
    [claim] = client.get("/api/v1/checkout", headers=auth_headers).json()["checked_promotions"]
    # «One, the largest»: the 10 % birthday loses to the automatic 15 %.
    assert claim["preview_total"] == cart["total"]
