"""Public API: query ILI, ARI and SARI rates and virological positivity.

Rate queries (``get_ili``, ``get_ari``, ``get_sari``, ``get_data``) return a long-format
DataFrame with one row per country, week and age group, sorted by country, date and age
group:

    indicator     "ili", "ari" or "sari"
    country       Country name as used by ECDC, e.g. "Czechia"
    country_code  ISO 3166-1 alpha-2 code, e.g. "CZ"
    year_week     ISO week, e.g. "2024-W40"
    date          Last day (Sunday) of the ISO week
    age           Age group: "0-4", "5-14", "15-64", "65+" or "total"
    value         The rate
    unit          What value is a rate of:
                  - "per 100,000 population" (SARI: hospital catchment population)
                  - "per 100,000 consultations": ILI/ARI in Cyprus, Finland,
                    Luxembourg, Malta
                  - "per 100,000 hospital admissions": SARI in Greece, Ireland,
                    Latvia, Luxembourg
                  Rates with different units are not directly comparable.
                  Slovakia's SARI data counts ICU admissions only.

``get_positivity`` returns the same layout with setting and pathogen columns, value in
percent, and the tests and detections counts the positivity is computed from.
"""

from __future__ import annotations

import difflib
from collections.abc import Iterable
from datetime import date

import pandas as pd

from .cache import clear_cache
from .data_loader import load_csv, update_data
from .exceptions import DataNotFoundError, InvalidParameterError
from .indicators import (
    INDICATORS,
    PATHOGEN_ALIASES,
    PATHOGENS,
    POSITIVITY_FILES,
    Indicator,
    get_indicator,
)
from .types import AGE_GROUPS, COUNTRY_ALIASES, COUNTRY_CODES
from .utils import parse_season, season_of, to_yearweek, yearweek_to_date

COLUMNS = [
    "indicator",
    "country",
    "country_code",
    "year_week",
    "date",
    "age",
    "value",
    "unit",
]
POSITIVITY_COLUMNS = [
    "indicator",
    "setting",
    "pathogen",
    "country",
    "country_code",
    "year_week",
    "date",
    "age",
    "value",
    "unit",
    "tests",
    "detections",
]
POSITIVITY = "positivity"

# Shared by get_data and the per-indicator functions, so their docs can't drift apart
_FILTER_ARGS = """
        countries: Country name(s) or ISO2 code(s), case-insensitive, e.g. "Italy" or
            ["FR", "Spain"]. Default: all countries.
        start: First week to include, as "2024-W40", "2024-10-01" or a date.
        end: Last week to include (inclusive), in the same formats.
        season: Season(s) such as "2024/25", which runs from 2024-W40 to 2025-W39.
            Cannot be combined with start/end.
        age_groups: Age group(s) among "0-4", "5-14", "15-64", "65+" and "total".
            Default: all. ILI/ARI data before 2022-W25 is only available for "total".
"""
_RETURNS_RAISES = """
    Returns:
        DataFrame with columns indicator ("ili", "ari" or "sari"), country,
        country_code, year_week, date (Sunday of the week), age, value (the rate) and
        unit (e.g. "per 100,000 population"). Empty if nothing matches.

    Raises:
        InvalidParameterError: Unknown indicator, country or age group, a malformed
            week or season, or season combined with start/end.
        DataNotFoundError: A requested country has no data for this indicator.
"""


def _query_doc(summary: str, indicator_arg: bool = False) -> str:
    indicator = '\n        indicator: "ili", "ari" or "sari".' if indicator_arg else ""
    return f"{summary}\n\n    Args:{indicator}{_FILTER_ARGS}{_RETURNS_RAISES}"


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
    ind = get_indicator(indicator)
    week_ranges = _week_ranges(start, end, season)
    ages = _resolve_age_groups(age_groups)

    df = _load(ind)
    if countries is not None:
        df = df[df["countryname"].isin(_resolve_countries(countries, ind.name, df))]
    if ages is not None:
        df = df[df["age"].isin(ages)]
    df = _filter_weeks(df, week_ranges)
    return _to_output(df, ind)


get_data.__doc__ = _query_doc("Get rates for an indicator, optionally filtered.", True)


def get_ili(
    countries: OneOrMany = None,
    start: WeekLike | None = None,
    end: WeekLike | None = None,
    season: OneOrMany = None,
    age_groups: OneOrMany = None,
) -> pd.DataFrame:
    return get_data("ili", countries, start, end, season, age_groups)


get_ili.__doc__ = _query_doc(
    "Weekly influenza-like illness (ILI) consultation rates (primary care)."
)


def get_ari(
    countries: OneOrMany = None,
    start: WeekLike | None = None,
    end: WeekLike | None = None,
    season: OneOrMany = None,
    age_groups: OneOrMany = None,
) -> pd.DataFrame:
    return get_data("ari", countries, start, end, season, age_groups)


get_ari.__doc__ = _query_doc(
    "Weekly acute respiratory infection (ARI) consultation rates (primary care)."
)


def get_sari(
    countries: OneOrMany = None,
    start: WeekLike | None = None,
    end: WeekLike | None = None,
    season: OneOrMany = None,
    age_groups: OneOrMany = None,
) -> pd.DataFrame:
    return get_data("sari", countries, start, end, season, age_groups)


get_sari.__doc__ = _query_doc(
    "Weekly severe acute respiratory infection (SARI) rates (hospitals; Slovakia: ICU)."
)


def get_positivity(
    pathogen: OneOrMany = None,
    setting: OneOrMany = None,
    countries: OneOrMany = None,
    start: WeekLike | None = None,
    end: WeekLike | None = None,
    season: OneOrMany = None,
) -> pd.DataFrame:
    """Weekly test positivity for influenza, RSV and SARS-CoV-2.

    Positivity is the percentage of tested samples that were positive. Primary care
    samples come from patients with ILI and/or ARI at sentinel GPs; hospital samples
    from SARI patients. Data is available for all ages combined only.

    Args:
        pathogen: "influenza", "rsv" or "sars-cov-2" (case-insensitive; "flu" and
            "covid" are accepted), or a list. Default: all three.
        setting: "primary care" or "hospital", or a list. Default: both.
        countries: Country name(s) or ISO2 code(s), case-insensitive. "EU/EEA" (code
            "EU") is ECDC's aggregate for the region. Default: all countries.
        start: First week to include, as "2024-W40", "2024-10-01" or a date.
        end: Last week to include (inclusive), in the same formats.
        season: Season(s) such as "2024/25", which runs from 2024-W40 to 2025-W39.
            Cannot be combined with start/end.

    Returns:
        DataFrame with columns indicator ("positivity"), setting, pathogen
        ("Influenza", "RSV" or "SARS-CoV-2"), country, country_code, year_week, date
        (Sunday of the week), age ("total"), value (positivity in percent), unit ("%"),
        tests and detections (the counts positivity is computed from; small numbers of
        tests make positivity noisy). Empty if nothing matches.

    Raises:
        InvalidParameterError: Unknown pathogen, setting or country, a malformed week
            or season, or season combined with start/end.
        DataNotFoundError: A requested country has no positivity data for the
            requested pathogens and settings.
    """
    pathogens = _resolve_pathogens(pathogen)
    settings = _resolve_settings(setting)
    week_ranges = _week_ranges(start, end, season)

    df = _load_positivity(settings)
    df = df[df["pathogen"].isin(pathogens)]
    if countries is not None:
        df = df[df["countryname"].isin(_resolve_countries(countries, POSITIVITY, df))]
    df = _filter_weeks(df, week_ranges)
    return _positivity_output(df)


def coverage(indicator: str) -> pd.DataFrame:
    """Per country: first and last week with data, number of weeks, and unit.

    Args:
        indicator: "ili", "ari", "sari" or "positivity".

    Returns:
        A DataFrame. For rates, one row per country with columns country, country_code,
        first_week, last_week, n_weeks (weeks with data in any age group), age_groups
        and unit. For positivity, one row per setting, pathogen and country with
        columns setting, pathogen, country, country_code, first_week, last_week,
        n_weeks and unit.
    """
    if _is_positivity(indicator):
        return _positivity_coverage()
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
    out["unit"] = out["country"].map(ind.unit)
    return out


def list_countries(indicator: str) -> list[str]:
    """Countries with data for an indicator ("ili", "ari", "sari" or "positivity")."""
    return sorted(_countries_and_weeks(indicator)["countryname"].unique())


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


def _is_positivity(name: str) -> bool:
    return isinstance(name, str) and name.lower() == POSITIVITY


def _load_positivity(settings: list[str]) -> pd.DataFrame:
    """Pathogen-level positivity, one row per setting, pathogen, country and week.

    Columns: setting, pathogen, countryname, yearweek, positivity, tests, detections.
    """
    frames = []
    for setting in settings:
        df = load_csv(POSITIVITY_FILES[setting])
        # Pathogen-level rows only: type and subtype rows have detections but no tests
        df = df[(df["pathogentype"] == df["pathogen"]) & (df["age"] == "total")]
        wide = df.pivot_table(
            index=["countryname", "yearweek", "pathogen"],
            columns="indicator",
            values="value",
            aggfunc="first",
        )
        wide = wide.reindex(columns=["positivity", "tests", "detections"])
        wide = wide[wide["positivity"].notna()].reset_index()
        wide.insert(0, "setting", setting)
        frames.append(wide)
    return pd.concat(frames, ignore_index=True)


def _countries_and_weeks(indicator: str) -> pd.DataFrame:
    """countryname and yearweek columns for an indicator, including positivity."""
    if _is_positivity(indicator):
        return _load_positivity(list(POSITIVITY_FILES))
    if isinstance(indicator, str) and indicator.lower() in INDICATORS:
        return _load(get_indicator(indicator))
    names = ", ".join([*INDICATORS, POSITIVITY])
    raise InvalidParameterError(f"Unknown indicator {indicator!r}; available: {names}")


def _all_weeks(indicator: str | None) -> set[str]:
    names = [indicator] if indicator is not None else [*INDICATORS, POSITIVITY]
    weeks: set[str] = set()
    for name in names:
        weeks.update(_countries_and_weeks(name)["yearweek"].unique())
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
    if season is not None and (start is not None or end is not None):
        raise InvalidParameterError("Use either season or start/end, not both")
    if season is not None:
        return [parse_season(s) for s in _as_list(season, "season")]
    if start is None and end is None:
        return []
    first = to_yearweek(start) if start is not None else "0000-W01"
    last = to_yearweek(end) if end is not None else "9999-W52"
    if first > last:
        raise InvalidParameterError(f"start ({first}) is after end ({last})")
    return [(first, last)]


def _filter_weeks(df: pd.DataFrame, week_ranges: list[tuple[str, str]]) -> pd.DataFrame:
    if not week_ranges:
        return df
    mask = pd.Series(False, index=df.index)
    for first, last in week_ranges:
        mask |= (df["yearweek"] >= first) & (df["yearweek"] <= last)
    return df[mask]


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


def _resolve_pathogens(pathogen: OneOrMany) -> list[str]:
    """ECDC pathogen names for the requested pathogens (all by default)."""
    if pathogen is None:
        return list(PATHOGENS.values())
    resolved = []
    for name in _as_list(pathogen, "pathogen"):
        key = name.strip().lower()
        key = PATHOGEN_ALIASES.get(key, key)
        if key not in PATHOGENS:
            raise InvalidParameterError(
                f"Unknown pathogen {name!r}; available: {', '.join(PATHOGENS)}"
            )
        resolved.append(PATHOGENS[key])
    return resolved


def _resolve_settings(setting: OneOrMany) -> list[str]:
    if setting is None:
        return list(POSITIVITY_FILES)
    resolved = []
    for name in _as_list(setting, "setting"):
        key = name.strip().lower()
        if key not in POSITIVITY_FILES:
            raise InvalidParameterError(
                f"Unknown setting {name!r}; available: {', '.join(map(repr, POSITIVITY_FILES))}"
            )
        resolved.append(key)
    return resolved


def _resolve_countries(
    countries: str | Iterable[str], indicator: str, df: pd.DataFrame
) -> list[str]:
    lookup = {name.lower(): name for name in COUNTRY_CODES}
    lookup.update({code.lower(): name for name, code in COUNTRY_CODES.items()})
    lookup.update({alias.lower(): name for alias, name in COUNTRY_ALIASES.items()})
    # Countries in the data but missing from COUNTRY_CODES are still accepted by name
    lookup.update({name.lower(): name for name in df["countryname"].unique()})

    available = set(df["countryname"].unique())
    label = indicator if indicator == POSITIVITY else indicator.upper()
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
                f"{name} has no {label} data; "
                f"use pyerviss.list_countries({indicator!r}) to see available countries"
            )
        resolved.append(name)
    return resolved


def _week_dates(year_weeks: pd.Series) -> pd.Series:
    week_dates = {week: pd.Timestamp(yearweek_to_date(week)) for week in year_weeks.unique()}
    return year_weeks.map(week_dates).astype("datetime64[ns]")


def _to_output(df: pd.DataFrame, ind: Indicator) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "indicator": ind.name,
            "country": df["countryname"],
            "country_code": df["countryname"].map(COUNTRY_CODES),
            "year_week": df["yearweek"],
            "date": _week_dates(df["yearweek"]),
            "age": df["age"],
            "value": df["value"],
            "unit": df["countryname"].map(ind.unit),
        },
        columns=COLUMNS,
    )
    age_order = out["age"].map({age: i for i, age in enumerate(AGE_GROUPS)})
    out = out.assign(_age_order=age_order).sort_values(["country", "date", "_age_order"])
    return out.drop(columns="_age_order").reset_index(drop=True)


def _positivity_output(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "indicator": POSITIVITY,
            "setting": df["setting"],
            "pathogen": df["pathogen"],
            "country": df["countryname"],
            "country_code": df["countryname"].map(COUNTRY_CODES),
            "year_week": df["yearweek"],
            "date": _week_dates(df["yearweek"]),
            "age": "total",
            "value": df["positivity"].astype("float64"),
            "unit": "%",
            "tests": df["tests"].round().astype("Int64"),
            "detections": df["detections"].round().astype("Int64"),
        },
        columns=POSITIVITY_COLUMNS,
    )
    out = out.sort_values(["setting", "pathogen", "country", "date"])
    return out.reset_index(drop=True)


def _positivity_coverage() -> pd.DataFrame:
    df = _load_positivity(list(POSITIVITY_FILES))
    grouped = df.groupby(["setting", "pathogen", "countryname"])
    out = pd.DataFrame(
        {
            "first_week": grouped["yearweek"].min(),
            "last_week": grouped["yearweek"].max(),
            "n_weeks": grouped["yearweek"].nunique(),
        }
    ).reset_index()
    out = out.rename(columns={"countryname": "country"})
    out.insert(3, "country_code", out["country"].map(COUNTRY_CODES))
    out["unit"] = "%"
    return out


__all__ = [
    "clear_cache",
    "coverage",
    "get_ari",
    "get_data",
    "get_ili",
    "get_positivity",
    "get_sari",
    "latest_week",
    "list_countries",
    "list_seasons",
    "update_data",
]
