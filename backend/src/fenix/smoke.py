"""Post-deploy smoke test of the public stand, run on the server after every deploy.

Usage: fenix-smoke https://fenix.example.ru

Walks the guest path through the public URL (Caddy, TLS, API, database) with launch
data signed by the bot token from the environment. Prints only check names and
statuses: no tokens, no launch data, no personal data.
"""

import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from fenix.platform.config import get_settings

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


def run(base_url: str) -> bool:
    token = get_settings().telegram_bot_token.get_secret_value()
    client = Client(base_url, signed_init_data(token))
    ok = True
    for name, check in CHECKS:
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
