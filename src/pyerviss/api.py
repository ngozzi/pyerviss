"""Public API: query ILI, ARI and SARI rates.

All query functions return a long-format DataFrame with one row per country, week and
age group, sorted by country, date and age group:

    country       Country name as used by ECDC, e.g. "Czechia"
    country_code  ISO 3166-1 alpha-2 code, e.g. "CZ"
    year_week     ISO week, e.g. "2024-W40"
    date          Last day (Sunday) of the ISO week
    age           Age group: "0-4", "5-14", "15-64", "65+" or "total"
    value         Rate per 100,000
    denominator   "population", or "consultations" for countries reporting per
                  consultation (Cyprus, Finland, Luxembourg, Malta for ILI/ARI)
"""

from __future__ import annotations

import difflib
from collections.abc import Iterable
from datetime import date

import pandas as pd

from .cache import clear_cache
from .data_loader import load_csv, update_data
from .exceptions import DataNotFoundError, InvalidParameterError
from .indicators import INDICATORS, Indicator, get_indicator
from .types import AGE_GROUPS, COUNTRY_ALIASES, COUNTRY_CODES
from .utils import parse_season, season_of, to_yearweek, yearweek_to_date

COLUMNS = ["country", "country_code", "year_week", "date", "age", "value", "denominator"]

WeekLike = str | date
OneOrMany = str | Iterable[str] | None


def get_data(
    indicator: str,
    countries: OneOrMany = None,
    start: WeekLike | None = None,
    end: WeekLike | None = None,
    season: OneOrMany = None,
    age_groups: OneOrMany = None,
) -> pd.DataFrame:
    """Get rates for an indicator, optionally filtered.

    Args:
        indicator: "ili", "ari" or "sari".
        countries: Country name(s) or ISO2 code(s), case-insensitive, e.g. "Italy",
            ["FR", "Spain"]. Default: all countries.
        start: First week to include, as "2024-W40", "2024-10-01" or a date.
        end: Last week to include (inclusive), in the same formats.
        season: Season(s) such as "2024/25", which runs from 2024-W40 to 2025-W39.
            Cannot be combined with start/end.
        age_groups: Age group(s) among "0-4", "5-14", "15-64", "65+", "total".
            Default: all. Data before 2022-W25 is only available for "total".

    Returns:
        DataFrame with columns country, country_code, year_week, date, age, value,
        denominator. Empty if nothing matches the filters.

    Raises:
        InvalidParameterError: Unknown indicator, country, age group, or malformed
            week/season, or season combined with start/end.
        DataNotFoundError: A requested country has no data for this indicator.
    """
    ind = get_indicator(indicator)
    if season is not None and (start is not None or end is not None):
        raise InvalidParameterError("Use either season or start/end, not both")
    week_ranges = _week_ranges(start, end, season)
    ages = _resolve_age_groups(age_groups)

    df = _load(ind)
    if countries is not None:
        df = df[df["countryname"].isin(_resolve_countries(countries, ind, df))]
    if ages is not None:
        df = df[df["age"].isin(ages)]
    if week_ranges:
        mask = pd.Series(False, index=df.index)
        for first, last in week_ranges:
            mask |= (df["yearweek"] >= first) & (df["yearweek"] <= last)
        df = df[mask]
    return _to_output(df, ind)


def get_ili(
    countries: OneOrMany = None,
    start: WeekLike | None = None,
    end: WeekLike | None = None,
    season: OneOrMany = None,
    age_groups: OneOrMany = None,
) -> pd.DataFrame:
    """Influenza-like illness (ILI) consultation rates. See ``get_data`` for details."""
    return get_data("ili", countries, start, end, season, age_groups)


def get_ari(
    countries: OneOrMany = None,
    start: WeekLike | None = None,
    end: WeekLike | None = None,
    season: OneOrMany = None,
    age_groups: OneOrMany = None,
) -> pd.DataFrame:
    """Acute respiratory infection (ARI) consultation rates. See ``get_data``."""
    return get_data("ari", countries, start, end, season, age_groups)


def get_sari(
    countries: OneOrMany = None,
    start: WeekLike | None = None,
    end: WeekLike | None = None,
    season: OneOrMany = None,
    age_groups: OneOrMany = None,
) -> pd.DataFrame:
    """Severe acute respiratory infection (SARI) rates. See ``get_data`` for details."""
    return get_data("sari", countries, start, end, season, age_groups)


def coverage(indicator: str) -> pd.DataFrame:
    """Per country: first and last week with data, number of weeks, and denominator.

    Weeks are counted if any age group has data. Columns: country, country_code,
    first_week, last_week, n_weeks, age_groups, denominator.
    """
    ind = get_indicator(indicator)
    df = _load(ind)
    grouped = df.groupby("countryname")
    out = pd.DataFrame(
        {
            "first_week": grouped["yearweek"].min(),
            "last_week": grouped["yearweek"].max(),
            "n_weeks": grouped["yearweek"].nunique(),
            "age_groups": grouped["age"].agg(
                lambda ages: [a for a in AGE_GROUPS if a in set(ages)]
            ),
        }
    ).reset_index(names="country")
    out.insert(1, "country_code", out["country"].map(COUNTRY_CODES))
    out["denominator"] = out["country"].map(ind.denominator)
    return out


def list_countries(indicator: str) -> list[str]:
    """Countries with data for an indicator, sorted by name."""
    return sorted(_load(get_indicator(indicator))["countryname"].unique())


def list_seasons(indicator: str | None = None) -> list[str]:
    """Seasons with data, e.g. ["2014/15", ..., "2026/27"]. Default: any indicator."""
    weeks = _all_weeks(indicator)
    return sorted({season_of(week) for week in weeks})


def latest_week(indicator: str | None = None) -> str:
    """Most recent week with data, e.g. "2026-W38". Default: across all indicators."""
    return max(_all_weeks(indicator))


# --- helpers ----------------------------------------------------------------


def _load(ind: Indicator) -> pd.DataFrame:
    df = load_csv(ind.data_file)
    return df[df["indicator"] == ind.ecdc_indicator]


def _all_weeks(indicator: str | None) -> set[str]:
    names = [indicator] if indicator is not None else list(INDICATORS)
    weeks: set[str] = set()
    for name in names:
        weeks.update(_load(get_indicator(name))["yearweek"].unique())
    if not weeks:
        raise DataNotFoundError("No data available")
    return weeks


def _as_list(value: str | Iterable[str], name: str) -> list[str]:
    message = f"{name} must be a string or a non-empty list of strings"
    try:
        values = [value] if isinstance(value, str) else list(value)
    except TypeError:
        raise InvalidParameterError(message) from None
    if not values or not all(isinstance(v, str) for v in values):
        raise InvalidParameterError(message)
    return values


def _week_ranges(
    start: WeekLike | None, end: WeekLike | None, season: OneOrMany
) -> list[tuple[str, str]]:
    if season is not None:
        return [parse_season(s) for s in _as_list(season, "season")]
    if start is None and end is None:
        return []
    first = to_yearweek(start) if start is not None else "0000-W01"
    last = to_yearweek(end) if end is not None else "9999-W52"
    if first > last:
        raise InvalidParameterError(f"start ({first}) is after end ({last})")
    return [(first, last)]


def _resolve_age_groups(age_groups: OneOrMany) -> list[str] | None:
    if age_groups is None:
        return None
    ages = _as_list(age_groups, "age_groups")
    unknown = [a for a in ages if a not in AGE_GROUPS]
    if unknown:
        raise InvalidParameterError(
            f"Unknown age group(s) {unknown}; available: {', '.join(AGE_GROUPS)}"
        )
    return ages


def _resolve_countries(
    countries: str | Iterable[str], ind: Indicator, df: pd.DataFrame
) -> list[str]:
    lookup = {name.lower(): name for name in COUNTRY_CODES}
    lookup.update({code.lower(): name for name, code in COUNTRY_CODES.items()})
    lookup.update({alias.lower(): name for alias, name in COUNTRY_ALIASES.items()})
    # Countries in the data but missing from COUNTRY_CODES are still accepted by name
    lookup.update({name.lower(): name for name in df["countryname"].unique()})

    available = set(df["countryname"].unique())
    resolved = []
    for country in _as_list(countries, "countries"):
        name = lookup.get(country.strip().lower())
        if name is None:
            close = difflib.get_close_matches(country.strip().lower(), lookup, n=3, cutoff=0.6)
            suggestions = list(dict.fromkeys(lookup[key] for key in close))
            hint = f"; did you mean {' or '.join(map(repr, suggestions))}?" if suggestions else ""
            raise InvalidParameterError(f"Unknown country {country!r}{hint}")
        if name not in available:
            raise DataNotFoundError(
                f"{name} has no {ind.name.upper()} data; "
                f"use pyerviss.list_countries({ind.name!r}) to see available countries"
            )
        resolved.append(name)
    return resolved


def _to_output(df: pd.DataFrame, ind: Indicator) -> pd.DataFrame:
    weeks = df["yearweek"].unique()
    week_dates = {week: pd.Timestamp(yearweek_to_date(week)) for week in weeks}
    out = pd.DataFrame(
        {
            "country": df["countryname"],
            "country_code": df["countryname"].map(COUNTRY_CODES),
            "year_week": df["yearweek"],
            "date": df["yearweek"].map(week_dates).astype("datetime64[ns]"),
            "age": df["age"],
            "value": df["value"],
            "denominator": df["countryname"].map(ind.denominator),
        },
        columns=COLUMNS,
    )
    age_order = out["age"].map({age: i for i, age in enumerate(AGE_GROUPS)})
    out = out.assign(_age_order=age_order).sort_values(["country", "date", "_age_order"])
    return out.drop(columns="_age_order").reset_index(drop=True)


__all__ = [
    "clear_cache",
    "coverage",
    "get_ari",
    "get_data",
    "get_ili",
    "get_sari",
    "latest_week",
    "list_countries",
    "list_seasons",
    "update_data",
]
