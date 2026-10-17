import json
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode

import pytest
from init_data import TEST_BOT_TOKEN, sign_init_data

from fenix.platform.messenger_auth import InvalidInitDataError, verify_telegram_init_data


def verify(init_data: str) -> object:
    return verify_telegram_init_data(init_data, TEST_BOT_TOKEN)


def test_valid_init_data() -> None:
    user = {"id": 42, "first_name": "Аня", "last_name": "К", "username": "anya"}
    launch = verify_telegram_init_data(sign_init_data(user, start_param="qr_table"), TEST_BOT_TOKEN)
    assert launch.external_id == "42"
    assert launch.first_name == "Аня"
    assert launch.last_name == "К"
    assert launch.username == "anya"
    assert launch.start_param == "qr_table"


def test_optional_fields_are_none() -> None:
    launch = verify_telegram_init_data(sign_init_data(), TEST_BOT_TOKEN)
    assert (launch.last_name, launch.username, launch.start_param) == (None, None, None)


def tamper(init_data: str, key: str, value: str) -> str:
    fields = dict(parse_qsl(init_data))
    fields[key] = value
    return urlencode(fields)


@pytest.mark.parametrize(
    "init_data",
    [
        pytest.param(
            tamper(sign_init_data(), "user", json.dumps({"id": 7, "first_name": "X"})), id="user"
        ),
        pytest.param(
            tamper(sign_init_data(), "auth_date", str(int(time.time()) + 1)), id="auth-date"
        ),
        pytest.param(sign_init_data() + "&start_param=promo", id="added-field"),
        pytest.param(sign_init_data(token="654321:OTHER-TOKEN"), id="other-bot"),
        pytest.param(sign_init_data(auth_date=int(time.time()) - 24 * 3600 - 1), id="expired"),
        pytest.param(sign_init_data(auth_date=int(time.time()) + 3600), id="from-future"),
        pytest.param(sign_init_data(auth_date="x"), id="auth-date-nan"),
        pytest.param(
            urlencode({k: v for k, v in parse_qsl(sign_init_data()) if k != "hash"}), id="no-hash"
        ),
        pytest.param(sign_init_data(raw_user="not json"), id="user-not-json"),
        pytest.param(sign_init_data({"id": True, "first_name": "X"}), id="id-not-int"),
        pytest.param(sign_init_data({"id": 1}), id="no-first-name"),
        pytest.param(sign_init_data() + "&hash=dup", id="duplicate-key"),
        pytest.param("%%%", id="garbage"),
        pytest.param("", id="empty"),
    ],
)
def test_rejected(init_data: str) -> None:
    with pytest.raises(InvalidInitDataError):
        verify(init_data)


def test_age_is_measured_from_now() -> None:
    signed_at = datetime(2026, 10, 16, 9, 0, tzinfo=UTC)
    init_data = sign_init_data(auth_date=int(signed_at.timestamp()))
    verify_telegram_init_data(init_data, TEST_BOT_TOKEN, now=signed_at + timedelta(hours=23))
    with pytest.raises(InvalidInitDataError):
        verify_telegram_init_data(
            init_data, TEST_BOT_TOKEN, now=signed_at + timedelta(hours=24, seconds=1)
        )
