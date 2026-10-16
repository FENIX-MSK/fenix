"""Build Telegram `initData` the way Telegram signs it, for tests."""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

TEST_BOT_TOKEN = "123456:TEST-TOKEN"


def sign_init_data(
    user: dict[str, object] | None = None,
    *,
    auth_date: int | str | None = None,
    raw_user: str | None = None,
    token: str = TEST_BOT_TOKEN,
    **extra: str,
) -> str:
    """Correctly signed launch data; `raw_user` / a str `auth_date` allow malformed values."""
    fields = {
        "auth_date": str(int(time.time()) if auth_date is None else auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": raw_user
        if raw_user is not None
        else json.dumps(user or {"id": 42, "first_name": "Аня"}, ensure_ascii=False),
        **extra,
    }
    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def sign_contact(user_id: int, phone: str, token: str = TEST_BOT_TOKEN) -> str:
    """A `requestContact` response as Telegram signs it."""
    fields = {
        "auth_date": str(int(time.time())),
        "contact": json.dumps({"user_id": user_id, "phone_number": phone, "first_name": "Аня"}),
    }
    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)
