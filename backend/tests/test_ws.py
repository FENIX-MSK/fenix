import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from init_data import sign_init_data
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.websockets import WebSocketDisconnect
from test_orders import add_to_cart, place

from fenix.main import create_app
from fenix.platform.config import Settings


@pytest.fixture
def client(ready_guest: async_sessionmaker[AsyncSession]) -> Iterator[TestClient]:
    with TestClient(create_app(Settings())) as client:
        yield client


def hello(init_data: str, channel: str) -> dict[str, Any]:
    return {"auth": init_data, "channel": channel}


def publish(channel: str, signal: dict[str, Any]) -> None:
    redis = Redis.from_url(Settings().redis_url)  # type: ignore[call-arg]
    try:
        redis.publish(channel, json.dumps(signal))
    finally:
        redis.close()


def test_guest_gets_signals_of_their_order(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    add_to_cart(client, auth_headers, "Капучино")
    order = place(client, auth_headers).json()
    with client.websocket_connect("/api/v1/ws") as ws:
        ws.send_json(hello(sign_init_data(), f"order:{order['id']}"))
        assert ws.receive_json() == {"event": "subscribed"}
        signal = {"event": "ordering.order.accepted", "order_id": order["id"], "status": "accepted"}
        publish(f"order:{order['id']}", signal)
        assert ws.receive_json() == signal


def test_someone_elses_order_is_forbidden(client: TestClient, auth_headers: dict[str, str]) -> None:
    add_to_cart(client, auth_headers, "Капучино")
    order = place(client, auth_headers).json()
    stranger = sign_init_data({"id": 7, "first_name": "Чужой"})
    with client.websocket_connect("/api/v1/ws") as ws:
        ws.send_json(hello(stranger, f"order:{order['id']}"))
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4403


def test_board_channel_is_for_staff(client: TestClient, staff_headers: dict[str, str]) -> None:
    with client.websocket_connect("/api/v1/ws") as ws:
        ws.send_json(hello(sign_init_data(), "staff"))
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4403
    staff = staff_headers["Authorization"].removeprefix("tma ")
    with client.websocket_connect("/api/v1/ws") as ws:
        ws.send_json(hello(f"tma {staff}", "staff"))
        assert ws.receive_json() == {"event": "subscribed"}


def test_bad_launch_data_is_rejected(client: TestClient) -> None:
    with client.websocket_connect("/api/v1/ws") as ws:
        ws.send_json(hello("hash=forged", "staff"))
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4401
