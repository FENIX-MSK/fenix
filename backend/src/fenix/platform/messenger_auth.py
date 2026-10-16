"""Verify Telegram Mini App launch data (`initData`), as described in the Bot API docs.

https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl

MAX_AGE = timedelta(hours=24)
# Small allowance for clock drift between Telegram and this server.
FUTURE_SKEW = timedelta(seconds=60)


class InvalidInitDataError(Exception):
    """The launch data is malformed, forged or expired. The reason is for logs only."""


@dataclass(frozen=True, slots=True)
class MessengerUser:
    external_id: str
    first_name: str
    last_name: str | None
    username: str | None
    start_param: str | None


def verify_telegram_init_data(
    init_data: str,
    bot_token: str,
    *,
    now: datetime | None = None,
    max_age: timedelta = MAX_AGE,
) -> MessengerUser:
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise InvalidInitDataError("not a query string") from exc
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise InvalidInitDataError("duplicate keys")

    received_hash = fields.pop("hash", None)
    if not received_hash:
        raise InvalidInitDataError("missing hash")
    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise InvalidInitDataError("bad signature")

    try:
        auth_date = datetime.fromtimestamp(int(fields["auth_date"]), UTC)
    except (KeyError, ValueError, OverflowError, OSError) as exc:
        raise InvalidInitDataError("bad auth_date") from exc
    now = now or datetime.now(UTC)
    if auth_date > now + FUTURE_SKEW or now - auth_date > max_age:
        raise InvalidInitDataError("expired")

    try:
        user = json.loads(fields["user"])
        external_id = user["id"]
        first_name = user["first_name"]
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidInitDataError("bad user") from exc
    if type(external_id) is not int or not isinstance(first_name, str):
        raise InvalidInitDataError("bad user")

    return MessengerUser(
        external_id=str(external_id),
        first_name=first_name,
        last_name=_optional_str(user.get("last_name")),
        username=_optional_str(user.get("username")),
        start_param=fields.get("start_param") or None,
    )


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
