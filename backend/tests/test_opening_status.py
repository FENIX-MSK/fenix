from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

import pytest

from fenix.modules.locations.hours import Interval, opening_status

MSK = ZoneInfo("Europe/Moscow")
DAILY = [Interval(d, time(9), time(22)) for d in range(7)]


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """Moscow time on a day of the week of 2026-10-12 (Monday) … 2026-10-18 (Sunday)."""
    return datetime(2026, 10, 12 + day, hour, minute, tzinfo=MSK)


def status_text(intervals: list[Interval], now: datetime) -> str:
    return opening_status(intervals, "Europe/Moscow", now).text


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (at(2, 12), "Открыто до 22:00"),
        (at(2, 7, 30), "Закрыто, откроемся в 9:00"),
        (at(2, 9), "Открыто до 22:00"),
        (at(2, 22), "Закрыто, откроемся завтра в 9:00"),
        (at(2, 23, 59), "Закрыто, откроемся завтра в 9:00"),
    ],
)
def test_daily_schedule(now: datetime, expected: str) -> None:
    assert status_text(DAILY, now) == expected


def test_open_status_carries_local_closing_time() -> None:
    status = opening_status(DAILY, "Europe/Moscow", at(2, 12))
    assert status.is_open
    assert status.closes_at == at(2, 22)
    assert status.opens_at is None


def test_closed_status_carries_local_opening_time() -> None:
    status = opening_status(DAILY, "Europe/Moscow", at(2, 23))
    assert not status.is_open
    assert status.opens_at == at(3, 9)


def test_after_midnight_interval() -> None:
    late_friday = [*DAILY[:4], Interval(4, time(18), time(2)), *DAILY[5:]]
    assert status_text(late_friday, at(5, 1)) == "Открыто до 2:00"
    assert status_text(late_friday, at(5, 2)) == "Закрыто, откроемся в 9:00"
    assert status_text(late_friday, at(4, 23)) == "Открыто до 2:00"


@pytest.mark.parametrize(
    ("days_off", "now", "expected"),
    [
        ({6}, at(5, 23), "Закрыто, откроемся в понедельник в 9:00"),
        ({0}, at(6, 23), "Закрыто, откроемся во вторник в 9:00"),
        ({1, 2}, at(0, 23), "Закрыто, откроемся в четверг в 9:00"),
        ({4, 5, 6}, at(3, 23), "Закрыто, откроемся в понедельник в 9:00"),
    ],
)
def test_days_off(days_off: set[int], now: datetime, expected: str) -> None:
    intervals = [i for i in DAILY if i.weekday not in days_off]
    assert status_text(intervals, now) == expected


def test_round_the_clock() -> None:
    always = [Interval(d, time(0), time(0)) for d in range(7)]
    assert status_text(always, at(3, 4)) == "Открыто круглосуточно"


def test_single_24h_day_closes_at_midnight() -> None:
    hours = [Interval(0, time(0), time(0)), Interval(1, time(9), time(22))]
    assert status_text(hours, at(0, 15)) == "Открыто до 0:00"


def test_back_to_back_intervals_read_as_one() -> None:
    hours = [Interval(0, time(0), time(0)), Interval(1, time(0), time(22))]
    assert status_text(hours, at(0, 15)) == "Открыто до 22:00"


def test_no_hours_is_closed() -> None:
    assert status_text([], at(2, 12)) == "Закрыто"


def test_server_clock_in_utc() -> None:
    # 06:30 UTC is 09:30 in Moscow.
    now = datetime(2026, 10, 14, 6, 30, tzinfo=UTC)
    assert status_text(DAILY, now) == "Открыто до 22:00"
