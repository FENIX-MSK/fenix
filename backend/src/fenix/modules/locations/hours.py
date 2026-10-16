"""Opening status of a location, computed in the location's time zone (AD-11). Pure code."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

# Accusative case with its preposition: «откроемся во вторник в 9:00».
_ON_WEEKDAY = (
    "в понедельник",
    "во вторник",
    "в среду",
    "в четверг",
    "в пятницу",
    "в субботу",
    "в воскресенье",
)


@dataclass(frozen=True, slots=True)
class Interval:
    weekday: int
    opens_at: time
    closes_at: time


@dataclass(frozen=True, slots=True)
class OpeningStatus:
    is_open: bool
    text: str
    # Local (zone-aware) moments; None when not applicable.
    closes_at: datetime | None
    opens_at: datetime | None


def format_time(moment: time | datetime) -> str:
    return f"{moment.hour}:{moment.minute:02d}"


def _occurrences(
    intervals: Iterable[Interval], first_day: date, days: int, zone: ZoneInfo
) -> list[tuple[datetime, datetime]]:
    by_weekday = {interval.weekday: interval for interval in intervals}
    result = []
    for offset in range(days):
        day = first_day + timedelta(days=offset)
        interval = by_weekday.get(day.weekday())
        if interval is None:
            continue
        start = datetime.combine(day, interval.opens_at, zone)
        end = datetime.combine(day, interval.closes_at, zone)
        if end <= start:
            end += timedelta(days=1)
        result.append((start, end))
    return result


def opening_status(intervals: Iterable[Interval], zone_name: str, now: datetime) -> OpeningStatus:
    zone = ZoneInfo(zone_name)
    local_now = now.astimezone(zone)
    today = local_now.date()
    intervals = list(intervals)

    if intervals and all(i.opens_at == i.closes_at for i in intervals) and len(intervals) == 7:
        return OpeningStatus(True, "Открыто круглосуточно", None, None)

    # Yesterday's interval may run past midnight into today.
    occurrences = _occurrences(intervals, today - timedelta(days=1), 9, zone)
    for start, end in occurrences:
        if start <= local_now < end:
            # Back-to-back intervals (e.g. 24 h days) read as one stretch.
            for next_start, next_end in occurrences:
                if next_start == end:
                    end = next_end
            return OpeningStatus(True, f"Открыто до {format_time(end)}", end, None)

    upcoming = [start for start, _ in occurrences if start > local_now]
    if not upcoming:
        return OpeningStatus(False, "Закрыто", None, None)
    opens = min(upcoming)
    if opens.date() == today:
        when = ""
    elif opens.date() == today + timedelta(days=1):
        when = "завтра "
    else:
        when = f"{_ON_WEEKDAY[opens.weekday()]} "
    return OpeningStatus(False, f"Закрыто, откроемся {when}в {format_time(opens)}", None, opens)
