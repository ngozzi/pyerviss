"""Tests for pyerviss.utils."""

from datetime import date, datetime, timedelta

import pytest

from pyerviss.exceptions import InvalidParameterError
from pyerviss.utils import (
    date_to_yearweek,
    parse_season,
    parse_yearweek,
    season_of,
    to_yearweek,
    yearweek_to_date,
)


def test_parse_yearweek():
    assert parse_yearweek("2024-W40") == (2024, 40)
    assert parse_yearweek("2020-W53") == (2020, 53)


@pytest.mark.parametrize("value", ["2024-40", "2024-W4", "24-W40", "2024-W00", "2024-W54", ""])
def test_parse_yearweek_rejects_malformed(value):
    with pytest.raises(InvalidParameterError, match="Invalid ISO week"):
        parse_yearweek(value)


def test_parse_yearweek_rejects_week_53_in_52_week_year():
    with pytest.raises(InvalidParameterError, match="does not exist"):
        parse_yearweek("2021-W53")


@pytest.mark.parametrize(
    "year_week, expected",
    [
        ("2024-W40", date(2024, 10, 6)),
        ("2025-W01", date(2025, 1, 5)),  # week 1 starts in the previous year (Dec 30)
        ("2020-W53", date(2021, 1, 3)),  # 53-week year ends in the next calendar year
    ],
)
def test_yearweek_to_date_returns_sunday(year_week, expected):
    result = yearweek_to_date(year_week)
    assert result == expected
    assert result.isoweekday() == 7


@pytest.mark.parametrize(
    "d, expected",
    [
        (date(2024, 9, 30), "2024-W40"),  # Monday
        (date(2024, 10, 6), "2024-W40"),  # Sunday
        (date(2024, 12, 30), "2025-W01"),  # ISO year differs from calendar year
        (date(2021, 1, 1), "2020-W53"),
    ],
)
def test_date_to_yearweek(d, expected):
    assert date_to_yearweek(d) == expected


def test_yearweek_date_round_trip():
    for year_week in ["2014-W40", "2015-W53", "2020-W53", "2026-W38"]:
        assert date_to_yearweek(yearweek_to_date(year_week)) == year_week


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2024-W40", "2024-W40"),
        ("2024-10-01", "2024-W40"),
        (date(2024, 10, 1), "2024-W40"),
        (datetime(2024, 10, 1, 15, 30), "2024-W40"),
    ],
)
def test_to_yearweek(value, expected):
    assert to_yearweek(value) == expected


@pytest.mark.parametrize("value", ["2024/10/01", "yesterday", "2021-W53", 202440, None])
def test_to_yearweek_rejects_invalid(value):
    with pytest.raises(InvalidParameterError):
        to_yearweek(value)


@pytest.mark.parametrize(
    "season, expected",
    [
        ("2024/25", ("2024-W40", "2025-W39")),
        ("2024/2025", ("2024-W40", "2025-W39")),
        ("1999/00", ("1999-W40", "2000-W39")),
        ("2020/21", ("2020-W40", "2021-W39")),  # includes 2020-W53
    ],
)
def test_parse_season(season, expected):
    assert parse_season(season) == expected


@pytest.mark.parametrize("season", ["2024/26", "2024-25", "2024", "24/25", "2024/2026"])
def test_parse_season_rejects_invalid(season):
    with pytest.raises(InvalidParameterError):
        parse_season(season)


def test_seasons_tile_without_gaps_or_overlaps():
    # The week after each season's last week is the next season's first week
    for start_year in range(2014, 2030):
        _, last = parse_season(f"{start_year}/{(start_year + 1) % 100:02d}")
        next_first, _ = parse_season(f"{start_year + 1}/{(start_year + 2) % 100:02d}")
        week_after = date_to_yearweek(yearweek_to_date(last) + timedelta(days=7))
        assert week_after == next_first


@pytest.mark.parametrize(
    "year_week, expected",
    [
        ("2024-W40", "2024/25"),
        ("2020-W53", "2020/21"),
        ("2025-W01", "2024/25"),
        ("2025-W39", "2024/25"),
        ("1999-W45", "1999/00"),
    ],
)
def test_season_of(year_week, expected):
    assert season_of(year_week) == expected
