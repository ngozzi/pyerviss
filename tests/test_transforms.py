"""Tests for pyerviss.transforms."""

import math

import pandas as pd
import pytest

import pyerviss as pv
from pyerviss.exceptions import InvalidParameterError


@pytest.mark.parametrize(
    "year_week, season, week",
    [
        ("2024-W40", "2024/25", 1),
        ("2024-W52", "2024/25", 13),
        ("2025-W01", "2024/25", 14),
        ("2025-W39", "2024/25", 52),
        ("2020-W53", "2020/21", 14),  # 53-week year
        ("2021-W01", "2020/21", 15),
        ("2021-W39", "2020/21", 53),  # the 2020/21 season has 53 weeks
    ],
)
def test_add_season_week(year_week, season, week):
    out = pv.add_season_week(pd.DataFrame({"year_week": [year_week], "value": [1.0]}))
    assert out.iloc[0][["season", "season_week"]].tolist() == [season, week]
    assert out["season_week"].dtype == "int64"


def test_add_season_week_returns_copy():
    df = pd.DataFrame({"year_week": ["2024-W40"]})
    pv.add_season_week(df)
    assert list(df.columns) == ["year_week"]


def test_add_season_week_requires_year_week():
    with pytest.raises(InvalidParameterError, match="year_week"):
        pv.add_season_week(pd.DataFrame({"week": ["2024-W40"]}))


def test_add_positivity_ci_matches_wilson_interval():
    df = pd.DataFrame({"tests": [184, 1, 1000], "detections": [59, 1, 0]})
    out = pv.add_positivity_ci(df)
    # Reference values for the 95% Wilson score interval
    assert out["ci_low"].round(2).tolist() == [25.75, 20.65, 0.0]
    assert out["ci_high"].round(2).tolist() == [39.12, 100.0, 0.38]


def test_add_positivity_ci_contains_positivity():
    df = pd.DataFrame({"tests": [10, 50, 300], "detections": [3, 25, 12]})
    out = pv.add_positivity_ci(df)
    positivity = df["detections"] / df["tests"] * 100
    assert ((out["ci_low"] <= positivity) & (positivity <= out["ci_high"])).all()


def test_add_positivity_ci_level():
    df = pd.DataFrame({"tests": [100], "detections": [30]})
    narrow = pv.add_positivity_ci(df, level=0.5).iloc[0]
    wide = pv.add_positivity_ci(df, level=0.99).iloc[0]
    assert wide["ci_low"] < narrow["ci_low"] < 30 < narrow["ci_high"] < wide["ci_high"]


def test_add_positivity_ci_missing_or_zero_tests():
    df = pd.DataFrame(
        {
            "tests": pd.array([0, None], dtype="Int64"),
            "detections": pd.array([0, None], dtype="Int64"),
        }
    )
    out = pv.add_positivity_ci(df)
    assert out[["ci_low", "ci_high"]].isna().all().all()


@pytest.mark.parametrize("level", [0, 1, 1.5, -0.1])
def test_add_positivity_ci_rejects_bad_level(level):
    with pytest.raises(InvalidParameterError, match="level"):
        pv.add_positivity_ci(pd.DataFrame({"tests": [1], "detections": [1]}), level=level)


def test_add_positivity_ci_requires_counts():
    with pytest.raises(InvalidParameterError, match="tests"):
        pv.add_positivity_ci(pd.DataFrame({"value": [1.0]}))


def test_wilson_interval_is_finite_for_all_positive():
    out = pv.add_positivity_ci(pd.DataFrame({"tests": [5], "detections": [5]}))
    assert math.isclose(out.iloc[0]["ci_high"], 100.0)
    assert 0 < out.iloc[0]["ci_low"] < 100
