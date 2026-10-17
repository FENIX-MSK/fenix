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


def verify_signed_query(
    raw: str,
    bot_token: str,
    *,
    now: datetime | None = None,
    max_age: timedelta = MAX_AGE,
) -> dict[str, str]:
    """Check a query string signed by Telegram the way it signs launch data
    (`initData`, shared contacts) and return its fields."""
    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
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
    return fields


@dataclass(frozen=True, slots=True)
class SharedContact:
    external_id: str
    phone: str


def verify_shared_contact(raw: str, bot_token: str) -> SharedContact:
    """The response of Telegram's `requestContact`, signed like launch data."""
    fields = verify_signed_query(raw, bot_token)
    try:
        contact = json.loads(fields["contact"])
        user_id, phone = contact["user_id"], contact["phone_number"]
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidInitDataError("bad contact") from exc
    if type(user_id) is not int or not isinstance(phone, str):
        raise InvalidInitDataError("bad contact")
    return SharedContact(external_id=str(user_id), phone=phone)


def verify_telegram_init_data(
    init_data: str,
    bot_token: str,
    *,
    now: datetime | None = None,
    max_age: timedelta = MAX_AGE,
) -> MessengerUser:
    fields = verify_signed_query(init_data, bot_token, now=now, max_age=max_age)

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
