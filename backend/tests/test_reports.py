"""Story 7.1: the sales report."""

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_orders import add_to_cart, place

from fenix.main import create_app
from fenix.modules.reporting.sales import bounds
from fenix.platform.config import Settings


@pytest.fixture
def client(ready_guest: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


def run(client: TestClient, staff: dict[str, str], order: Any, *actions: str, **last: Any) -> Any:
    current = order
    for action in actions:
        body = {"action": action, "expected_version": current["version"]}
        if action == actions[-1]:
            body |= last
        current = client.post(
            f"/api/v1/staff/orders/{order['id']}/actions", headers=staff, json=body
        ).json()
    return current


def test_sales_report(
    client: TestClient, auth_headers: dict[str, str], staff_headers: dict[str, str]
) -> None:
    add_to_cart(client, auth_headers, "Капучино", 2)
    first = place(client, auth_headers).json()
    run(
        client,
        staff_headers,
        first,
        "accept",
        "start_cooking",
        "mark_ready",
        "hand_over",
        paid_with="card",
    )
    add_to_cart(client, auth_headers, "Филадельфия")
    second = place(client, auth_headers).json()
    run(
        client,
        staff_headers,
        second,
        "accept",
        "start_cooking",
        "mark_ready",
        "hand_over",
        paid_with="cash",
    )
    add_to_cart(client, auth_headers, "Капучино")
    third = place(client, auth_headers).json()
    run(client, staff_headers, third, "cancel", note="Нет продуктов")

    report = client.get("/api/v1/staff/reports/sales?period=day", headers=staff_headers).json()
    assert report["revenue"] == first["total"] + second["total"]
    assert report["completed"] == 2
    assert report["orders"] == 3
    assert report["average_check"] == (first["total"] + second["total"]) // 2
    assert report["cancelled"] == 1
    assert report["cancel_reasons"] == {"Нет продуктов": 1}
    assert report["by_payment"] == {"card": first["total"], "cash": second["total"]}
    assert report["by_fulfilment"] == {"pickup": 2}
    assert report["top_dishes"][0]["quantity"] == 2
    assert report["new_guests"]
    assert client.get("/api/v1/staff/reports/sales", headers=auth_headers).status_code == 403


def test_custom_period_validation(client: TestClient, staff_headers: dict[str, str]) -> None:
    bad = client.get(
        "/api/v1/staff/reports/sales?period=custom&start=2026-10-10&end=2026-10-01",
        headers=staff_headers,
    )
    assert bad.json()["error"]["code"] == "bad_period"
    ok = client.get(
        "/api/v1/staff/reports/sales?period=custom&start=2026-10-01&end=2026-10-10",
        headers=staff_headers,
    ).json()
    assert ok["start"] == "2026-10-01" and ok["end"] == "2026-10-10"


def test_bounds_are_local_midnights() -> None:
    start, end = bounds(date(2026, 10, 17), date(2026, 10, 17), "Europe/Moscow")
    assert start.isoformat() == "2026-10-17T00:00:00+03:00"
    assert end.isoformat() == "2026-10-18T00:00:00+03:00"
