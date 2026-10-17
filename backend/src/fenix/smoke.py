"""Post-deploy smoke test of the public stand, run on the server after every deploy.

Usage: fenix-smoke https://fenix.example.ru

Walks the guest path through the public URL (Caddy, TLS, API, database) with launch
data signed by the bot token from the environment. Prints only check names and
statuses: no tokens, no launch data, no personal data.
"""

import asyncio
import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from websockets.asyncio.client import connect

from fenix.modules.identity import api as identity
from fenix.modules.locations import api as locations
from fenix.modules.ordering import api as ordering
from fenix.modules.payments import api as payments
from fenix.platform.config import get_settings
from fenix.platform.db import create_engine, create_session_factory
from fenix.platform.storage import S3Storage

# A synthetic Telegram account: real ids are positive, this one cannot collide.
SMOKE_USER = {"id": 1, "first_name": "Smoke", "username": "fenix_smoke"}
TIMEOUT = 15


class SmokeError(Exception):
    pass


def signed_init_data(bot_token: str) -> str:
    fields = {
        "auth_date": str(int(time.time())),
        "query_id": "smoke",
        "user": json.dumps(SMOKE_USER, separators=(",", ":")),
        "start_param": "smoke",
    }
    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class Client:
    def __init__(self, base_url: str, init_data: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.authorization = f"tma {init_data}"

    def request(
        self, method: str, path: str, body: Any = None, *, auth: bool = True
    ) -> tuple[int, Any]:
        headers = {"Accept": "application/json"}
        if auth:
            headers["Authorization"] = self.authorization
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(  # noqa: S310 - the base URL is ours
            self.base_url + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
                raw = response.read()
                status = response.status
        except urllib.error.HTTPError as exc:
            raw, status = exc.read(), exc.code
        return status, json.loads(raw) if raw else None

    def get(self, path: str, *, auth: bool = True) -> Any:
        status, body = self.request("GET", path, auth=auth)
        if status != 200:
            raise SmokeError(f"GET {path} -> {status}")
        return body

    def post(self, path: str, body: Any) -> Any:
        status, payload = self.request("POST", path, body)
        if status != 200:
            raise SmokeError(f"POST {path} -> {status}")
        return payload


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)


def check_health(client: Client) -> None:
    expect(client.get("/api/health", auth=False) == {"status": "ok"}, "health is not ok")


def check_auth(client: Client) -> None:
    status, body = client.request("GET", "/api/v1/me", auth=False)
    expect(status == 401 and body["error"]["code"] == "unauthorized", "unsigned request passed")
    expect(client.get("/api/v1/me")["first_name"] == "Smoke", "signed request failed")


def check_location(client: Client) -> None:
    location = client.get("/api/v1/location")
    expect(location["status"]["text"].startswith(("Открыто", "Закрыто")), "no opening status")
    expect(len(location["opening_hours"]) > 0, "no opening hours")


def check_menu_and_price(client: Client) -> None:
    menu = client.get("/api/v1/menu")
    expect(len(menu["categories"]) >= 10, "menu is not seeded")
    dishes = [d for c in menu["categories"] for d in c["dishes"] if not d["sold_out"]]
    expect(len(dishes) > 0, "every dish is sold out")
    dish = client.get(f"/api/v1/menu/dishes/{dishes[0]['id']}")
    size = next(s for s in dish["sizes"] if s["available"])
    price = client.post(
        "/api/v1/menu/price",
        {"dish_id": dish["id"], "size_id": size["id"], "modifier_ids": [], "quantity": 2},
    )
    expect(price["unit_price"] > 0 and price["total_price"] == price["unit_price"] * 2, "bad price")


def check_staff_is_closed(client: Client) -> None:
    status, body = client.request("GET", "/api/v1/staff/me")
    expect(status == 403 and body["error"]["code"] == "forbidden", "staff API open to a guest")


CHECKS: list[tuple[str, Callable[[Client], None]]] = [
    ("health", check_health),
    ("auth", check_auth),
    ("location", check_location),
    ("menu-and-price", check_menu_and_price),
    ("staff-is-closed", check_staff_is_closed),
]


def check_staff_section(client: Client) -> None:
    catalog = client.get("/api/v1/staff/catalog")
    expect(len(catalog["categories"]) >= 10, "staff catalog is empty")
    members = client.get("/api/v1/staff/members")
    expect(any(m["is_me"] for m in members), "smoke user is not in the staff list")
    stop_list = client.get("/api/v1/staff/stop-list")
    size = next(s for d in stop_list["dishes"] for s in d["sizes"] if not s["stopped"])
    # Reversible: off and straight back on.
    for stopped in (True, False):
        status, _ = client.request(
            "PUT", "/api/v1/staff/stop-list", {"size_id": size["id"], "stopped": stopped}
        )
        expect(status == 200, f"stop-list toggle -> {status}")


def fetch(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url)  # noqa: S310 - our own public URL
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
        return response.read(), response.headers.get("Cache-Control", "")


async def check_media(client: Client) -> None:
    """Garage behind Caddy: an object put over S3 is served from /media/."""
    storage = S3Storage(get_settings())
    key = f"smoke/{uuid.uuid4()}.txt"
    await storage.put(key, b"smoke", "text/plain")
    try:
        body, cache = await asyncio.to_thread(fetch, f"{client.base_url}/media/{key}")
        expect(body == b"smoke", "media body differs")
        expect("immutable" in cache, "no long cache")
    finally:
        await storage.delete(key)


# The board and order screens must hear about a change within this (NFR-4).
SIGNAL_SECONDS = 5.0


async def check_order(client: Client) -> None:
    """Order -> outbox -> worker -> Redis -> WebSocket through Caddy (stories 3.3-3.10).

    An online order that is never paid: the staff chat hears nothing, and the order is
    cancelled by the system the way an unpaid one would be.
    """
    if not client.get("/api/v1/checkout")["is_open"]:
        print("     order: the cafe is closed now, checked only up to checkout", flush=True)
        return
    client.post(
        "/api/v1/me/contact", {"phone": "+70000000001", "first_name": "Smoke", "consent": True}
    )
    menu = client.get("/api/v1/menu")
    dish_ref = next(d for c in menu["categories"] for d in c["dishes"] if not d["sold_out"])
    dish = client.get(f"/api/v1/menu/dishes/{dish_ref['id']}")
    size = next(s for s in dish["sizes"] if s["available"])
    client.post(
        "/api/v1/cart/items",
        {"dish_id": dish["id"], "size_id": size["id"], "modifier_ids": [], "quantity": 1},
    )
    order = client.post("/api/v1/orders", {"payment_method": "online", "comment": "smoke"})
    expect(order["status"] == "pending_payment" and order["payment_id"], "no online payment")

    ws_url = client.base_url.replace("https://", "wss://").replace("http://", "ws://")
    async with connect(f"{ws_url}/api/v1/ws", open_timeout=TIMEOUT) as socket:
        hello = {"auth": client.authorization, "channel": f"order:{order['id']}"}
        await socket.send(json.dumps(hello))
        subscribed = json.loads(await asyncio.wait_for(socket.recv(), TIMEOUT))
        expect(subscribed == {"event": "subscribed"}, "websocket did not subscribe")

        declined = await asyncio.to_thread(
            client.post, f"/api/v1/payments/{order['payment_id']}/test-result", {"succeeded": False}
        )
        expect(declined["payment_status"] == "failed", "declined payment not recorded")

        engine = create_engine(get_settings().database_url)
        try:
            async with create_session_factory(engine)() as session, session.begin():
                await payments.cancel_pending(session, uuid.UUID(order["id"]))
                cancelled = await ordering.cancel_unpaid(
                    session, uuid.UUID(order["id"]), datetime.now(UTC)
                )
            expect(cancelled, "smoke order could not be cancelled")
        finally:
            await engine.dispose()

        deadline = time.monotonic() + SIGNAL_SECONDS
        while True:
            left = deadline - time.monotonic()
            expect(left > 0, f"no cancel signal within {SIGNAL_SECONDS:.0f} s (worker down?)")
            signal = json.loads(await asyncio.wait_for(socket.recv(), left))
            if signal.get("event") == "ordering.order.cancelled":
                break
    final = await asyncio.to_thread(client.get, f"/api/v1/orders/{order['id']}")
    expect(final["status"] == "cancelled", "order is not cancelled")


async def as_staff(check: Callable[[Client], None], client: Client) -> None:
    """Run a staff check with a temporary membership that is always removed."""
    engine = create_engine(get_settings().database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as session, session.begin():
            user = await identity.find_user(
                session, identity.Platform.TELEGRAM, str(SMOKE_USER["id"])
            )
            location_id = await locations.get_default_location_id(session)
            if user is None or location_id is None:
                raise SmokeError("smoke user or location missing")
            await identity.grant_staff(session, user.id, location_id)
        try:
            await asyncio.to_thread(check, client)
        finally:
            async with factory() as session, session.begin():
                await identity.remove_staff_membership(session, user.id, location_id)
    finally:
        await engine.dispose()


def run(base_url: str) -> bool:
    token = get_settings().telegram_bot_token.get_secret_value()
    client = Client(base_url, signed_init_data(token))
    ok = True
    checks: list[tuple[str, Callable[[Client], None]]] = [
        *CHECKS,
        ("staff-section", lambda c: asyncio.run(as_staff(check_staff_section, c))),
        ("media", lambda c: asyncio.run(check_media(c))),
        ("order-realtime", lambda c: asyncio.run(check_order(c))),
    ]
    for name, check in checks:
        try:
            check(client)
        # Report every failing check, then fail.
        except Exception as exc:
            ok = False
            print(f"FAIL {name}: {exc}", flush=True)
        else:
            print(f"ok   {name}", flush=True)
    return ok


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].startswith(("https://", "http://")):
        sys.exit("usage: fenix-smoke https://<site>")
    sys.exit(0 if run(sys.argv[1]) else 1)


if __name__ == "__main__":
    main()
