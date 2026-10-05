"""Helpers that add derived columns to query results."""

from __future__ import annotations

from statistics import NormalDist

import numpy as np
import pandas as pd

from .exceptions import InvalidParameterError
from .utils import SEASON_START_WEEK, parse_yearweek, season_of, yearweek_to_date


def add_season_week(df: pd.DataFrame) -> pd.DataFrame:
    """Add the season and the week of the season to each row.

    A season "2024/25" runs from 2024-W40 to 2025-W39. Its weeks are numbered from 1
    (W40) to 52, or 53 in seasons containing an ISO week 53.

    Args:
        df: A query result, or any DataFrame with a ``year_week`` column.

    Returns:
        A copy of ``df`` with ``season`` (e.g. "2024/25") and ``season_week`` (int)
        columns added.
    """
    _require_columns(df, ["year_week"], "add_season_week")
    weeks = pd.Series(df["year_week"].unique())
    seasons = {week: season_of(week) for week in weeks}
    numbers = {week: _season_week(week) for week in weeks}
    out = df.copy()
    out["season"] = out["year_week"].map(seasons)
    out["season_week"] = out["year_week"].map(numbers).astype("int64")
    return out


def add_positivity_ci(df: pd.DataFrame, level: float = 0.95) -> pd.DataFrame:
    """Add a confidence interval for positivity, computed from tests and detections.

    Uses the Wilson score interval, which stays sensible for small numbers of tests
    (1 positive out of 1 test gives roughly 21% to 100%, not a confident 100%).

    Args:
        df: A result of ``get_positivity``, or any DataFrame with ``tests`` and
            ``detections`` columns.
        level: Confidence level, between 0 and 1. Default 0.95.

    Returns:
        A copy of ``df`` with ``ci_low`` and ``ci_high`` columns, in percent. They are
        missing (NaN) where tests are missing or zero.
    """
    _require_columns(df, ["tests", "detections"], "add_positivity_ci")
    if not 0 < level < 1:
        raise InvalidParameterError(f"level must be between 0 and 1, got {level!r}")

    z = NormalDist().inv_cdf((1 + level) / 2)
    n = pd.to_numeric(df["tests"], errors="coerce").astype("float64")
    x = pd.to_numeric(df["detections"], errors="coerce").astype("float64")
    n = n.where(n > 0)
    p = (x / n).clip(0, 1)
    denominator = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denominator
    half_width = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator

    out = df.copy()
    out["ci_low"] = ((center - half_width).clip(lower=0) * 100).astype("float64")
    out["ci_high"] = ((center + half_width).clip(upper=1) * 100).astype("float64")
    return out


def _season_week(year_week: str) -> int:
    """Week of the season: W40 -> 1, ..., W39 of the next year -> 52 or 53."""
    year, week = parse_yearweek(year_week)
    start_year = year if week >= SEASON_START_WEEK else year - 1
    season_start = yearweek_to_date(f"{start_year}-W{SEASON_START_WEEK:02d}")
    return (yearweek_to_date(year_week) - season_start).days // 7 + 1


def _require_columns(df: pd.DataFrame, columns: list[str], caller: str) -> None:
    if not isinstance(df, pd.DataFrame):
        raise InvalidParameterError(f"{caller} expects a pandas DataFrame")
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise InvalidParameterError(
            f"{caller} needs column(s) {missing}; pass a result of a pyerviss query"
        )
