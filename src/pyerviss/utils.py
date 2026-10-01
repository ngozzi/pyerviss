"""ISO week and season helpers.

Weeks are ISO 8601 weeks written "YYYY-Www" (e.g. "2024-W40"). The date of a week is
its last day, Sunday, matching RespiCast's ``truth_date``. A season "2024/25" runs from
2024-W40 to 2025-W39.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from .exceptions import InvalidParameterError

SEASON_START_WEEK = 40

_YEARWEEK = re.compile(r"^(\d{4})-W(0[1-9]|[1-4]\d|5[0-3])$")
_SEASON = re.compile(r"^(\d{4})/(\d{2}|\d{4})$")


def parse_yearweek(year_week: str) -> tuple[int, int]:
    """Split "2024-W40" into (2024, 40), checking that the week exists."""
    match = _YEARWEEK.match(year_week)
    if not match:
        raise InvalidParameterError(f"Invalid ISO week {year_week!r}; expected e.g. '2024-W40'")
    year, week = int(match[1]), int(match[2])
    try:
        date.fromisocalendar(year, week, 1)
    except ValueError:
        raise InvalidParameterError(f"Week {year_week!r} does not exist") from None
    return year, week


def yearweek_to_date(year_week: str) -> date:
    """Last day (Sunday) of an ISO week: "2024-W40" -> date(2024, 10, 6)."""
    year, week = parse_yearweek(year_week)
    return date.fromisocalendar(year, week, 7)


def date_to_yearweek(d: date) -> str:
    """ISO week containing a date: date(2024, 10, 1) -> "2024-W40"."""
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def to_yearweek(value: str | date) -> str:
    """Normalize a week given as "2024-W40", "2024-10-01", a date or a datetime."""
    if isinstance(value, datetime):
        return date_to_yearweek(value.date())
    if isinstance(value, date):
        return date_to_yearweek(value)
    if isinstance(value, str):
        if _YEARWEEK.match(value):
            parse_yearweek(value)
            return value
        try:
            return date_to_yearweek(date.fromisoformat(value))
        except ValueError:
            pass
    raise InvalidParameterError(
        f"Invalid week or date {value!r}; expected e.g. '2024-W40', '2024-10-01' or a date"
    )


def parse_season(season: str) -> tuple[str, str]:
    """First and last week of a season: "2024/25" -> ("2024-W40", "2025-W39")."""
    match = _SEASON.match(season)
    if not match:
        raise InvalidParameterError(f"Invalid season {season!r}; expected e.g. '2024/25'")
    start_year, end = int(match[1]), match[2]
    end_year = start_year + 1
    if int(end) != (end_year if len(end) == 4 else end_year % 100):
        raise InvalidParameterError(
            f"Invalid season {season!r}; years must be consecutive, e.g. '2024/25'"
        )
    first = f"{start_year}-W{SEASON_START_WEEK:02d}"
    last_day = date.fromisocalendar(end_year, SEASON_START_WEEK, 1) - timedelta(days=1)
    return first, date_to_yearweek(last_day)


def season_of(year_week: str) -> str:
    """Season a week belongs to: "2024-W40" -> "2024/25", "2025-W39" -> "2024/25"."""
    year, week = parse_yearweek(year_week)
    start_year = year if week >= SEASON_START_WEEK else year - 1
    return f"{start_year}/{(start_year + 1) % 100:02d}"
