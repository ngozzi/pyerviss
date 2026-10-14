"""Conversion of ECDC's per-100 rates to per 100,000.

Shared by the daily sync (scripts/sync_ecdc.py), the history import and the vintage
loader, so that mirrored and snapshot values use the same units.
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from datetime import date

import pandas as pd

# ECDC: "ILI and ARI consultation rates are calculated per 100 000 population, except
# for Cyprus, Luxembourg, Malta (per 100 consultations) and Finland (per 100 000
# consultations)." and "SARI rates are calculated per 100 000 hospital catchment
# population, except for Greece, Ireland, Latvia and Luxembourg (per 100 total hospital
# admissions). Data from Slovakia are based on ICU admissions."
# Multiplying the per-100 countries by 1000 puts every value per 100,000 of its
# denominator; the denominator itself still differs by country.
_PER_100_CONSULTATIONS = frozenset({"Cyprus", "Luxembourg", "Malta"})
_PER_100_ADMISSIONS = frozenset({"Greece", "Ireland", "Latvia", "Luxembourg"})
PER_100_COUNTRIES: Mapping[str, Set[str]] = {
    "ILIconsultationrate": _PER_100_CONSULTATIONS,
    "ARIconsultationrate": _PER_100_CONSULTATIONS,
    "SARIrate": _PER_100_ADMISSIONS,
}
RESCALE_FACTOR = 1000

# Until 2025-10-24 ECDC published Greece and Latvia SARI rates already per 100,000
# hospital admissions (exactly 1000x the per-100 values it publishes since), so data
# published before that date must not be rescaled for them
PER_100K_UNTIL = date(2025, 10, 24)
PER_100K_BEFORE_SWITCH: Mapping[str, Set[str]] = {"SARIrate": frozenset({"Greece", "Latvia"})}


def normalize_units(
    df: pd.DataFrame, already_per_100k: Mapping[str, Set[str]] | None = None
) -> pd.DataFrame:
    """Convert rates ECDC publishes per 100 (consultations/admissions) to per 100,000.

    Args:
        df: Rows in ECDC's layout (indicator, countryname and value columns).
        already_per_100k: Indicator -> countries to leave unchanged because this version
            of the data already has them per 100,000.
    """
    mask = pd.Series(False, index=df.index)
    for indicator, countries in PER_100_COUNTRIES.items():
        skip = (already_per_100k or {}).get(indicator, frozenset())
        mask |= (df["indicator"] == indicator) & df["countryname"].isin(set(countries) - skip)
    if not mask.any():
        return df
    df = df.copy()
    # Round away float noise from the multiplication (e.g. 2.9 * 1000 = 2900.0000000000005)
    df.loc[mask, "value"] = (df.loc[mask, "value"] * RESCALE_FACTOR).round(9)
    return df


def normalize_snapshot(df: pd.DataFrame, vintage: date) -> pd.DataFrame:
    """Like normalize_units, for data ECDC published on the date ``vintage``."""
    return normalize_units(df, PER_100K_BEFORE_SWITCH if vintage < PER_100K_UNTIL else None)
