"""WebSocket signals for the staff board and the guest's order screen (AD-5).

The first client message authenticates and picks a channel:
`{"auth": "<initData>", "channel": "staff" | "order:<order_id>"}`. After that the server
only pushes signals `{"event", "order_id", "status", "version"}`; the client re-reads the
state through REST. Close codes: 4401 bad launch data, 4403 not allowed, 4400 bad hello.
"""

import asyncio
import contextlib
import json
import uuid

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fenix.http.auth import authenticate
from fenix.modules.identity import api as identity
from fenix.modules.locations import api as locations
from fenix.modules.ordering import api as ordering
from fenix.platform import realtime
from fenix.platform.config import Settings
from fenix.platform.errors import ApiError

log = structlog.get_logger()

router = APIRouter()

HELLO_TIMEOUT = 10.0
PING_SECONDS = 25.0


async def resolve_channel(
    session: AsyncSession, settings: Settings, hello: object
) -> tuple[str | None, int]:
    """The Redis channel this client may listen to, or a close code."""
    if not isinstance(hello, dict):
        return None, 4400
    auth, channel = hello.get("auth"), hello.get("channel")
    if not isinstance(auth, str) or not isinstance(channel, str):
        return None, 4400
    try:
        user = await authenticate(session, settings, auth.removeprefix("tma "))
    except ApiError:
        return None, 4401
    location_id = await locations.get_default_location_id(session)
    if location_id is None:
        return None, 4403
    staff = await identity.is_staff(session, user.id, location_id)
    if channel == "staff":
        return (realtime.staff_channel(location_id), 0) if staff else (None, 4403)
    if channel.startswith("order:"):
        try:
            order_id = uuid.UUID(channel.removeprefix("order:"))
        except ValueError:
            return None, 4400
        order = await ordering.get_order(session, order_id)
        # A guest listens to their own order only (FR-16); staff to any of the location.
        if order is None or not (
            order.user_id == user.id or (staff and order.location_id == location_id)
        ):
            return None, 4403
        return realtime.order_channel(order_id), 0
    return None, 4400


@router.websocket("/api/v1/ws")
async def signals(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        hello = await asyncio.wait_for(websocket.receive_json(), HELLO_TIMEOUT)
    except TimeoutError, WebSocketDisconnect, json.JSONDecodeError, ValueError:
        await websocket.close(4400)
        return
    factory: async_sessionmaker[AsyncSession] = websocket.app.state.session_factory
    settings: Settings = websocket.app.state.settings
    async with factory() as session, session.begin():
        channel, code = await resolve_channel(session, settings, hello)
    if channel is None:
        await websocket.close(code)
        return

    redis: Redis = websocket.app.state.redis
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    await websocket.send_json({"event": "subscribed"})

    async def relay() -> None:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"].decode())

    async def keepalive() -> None:
        # Proxies drop idle connections; a ping also reveals a dead client.
        while True:
            await asyncio.sleep(PING_SECONDS)
            await websocket.send_json({"event": "ping"})

    async def drain() -> None:
        # Clients send nothing after the hello; reading notices the disconnect.
        while True:
            await websocket.receive_text()

    tasks = [asyncio.create_task(job()) for job in (relay, keepalive, drain)]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(BaseException):
                await task
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()  # type: ignore[no-untyped-call]
        with contextlib.suppress(Exception):
            await websocket.close()
