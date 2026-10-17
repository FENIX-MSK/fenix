"""Real-time signals (AD-5): the worker publishes to Redis, every API process relays to
its WebSocket clients. A signal only says what changed; clients re-read through REST."""

import json
import uuid
from typing import Any

from redis.asyncio import Redis


def staff_channel(location_id: uuid.UUID | str) -> str:
    return f"staff:{location_id}"


def order_channel(order_id: uuid.UUID | str) -> str:
    return f"order:{order_id}"


async def publish(redis: Redis, channel: str, signal: dict[str, Any]) -> None:
    await redis.publish(channel, json.dumps(signal))
