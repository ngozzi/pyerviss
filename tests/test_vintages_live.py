"""Checks against real ECDC snapshots and the mirror. Run with: pytest -m live"""

import pandas as pd
import pytest

import pyerviss as pv

pytestmark = pytest.mark.live


def median_ratios(snapshot: pd.DataFrame, current: pd.DataFrame) -> pd.Series:
    """Median snapshot/mirror ratio per country and indicator, on shared non-zero weeks."""
    key = ["indicator", "country", "year_week", "age"]
    joined = snapshot[snapshot["vintage"].notna()].merge(current, on=key)
    joined = joined[(joined["value_x"] > 0) & (joined["value_y"] > 0)]
    ratios = joined["value_x"] / joined["value_y"]
    return ratios.groupby([joined["indicator"], joined["country"]]).median()


@pytest.mark.parametrize(
    ("indicator", "as_of"),
    [
        ("ili", None),
        ("ari", None),
        ("sari", None),
        # Greece and Latvia SARI were still published per 100,000 then
        ("sari", "2025-10-17"),
    ],
)
def test_snapshot_units_match_mirror(indicator, as_of):
    as_of = as_of or pv.list_vintages(indicator)[-1]
    ratios = median_ratios(pv.get_data(indicator, as_of=as_of), pv.get_data(indicator))
    assert not ratios.empty
    off = ratios[(ratios < 1 / 3) | (ratios > 3)]
    assert off.empty, f"Units differ from the mirror as of {as_of}:\n{off}"
