"""Indicator registry.

To add an indicator, register an ``Indicator`` here and make sure the sync script
mirrors its data file.
"""

from __future__ import annotations

from types import MappingProxyType

from ..exceptions import InvalidParameterError
from ..types import DATA_FILES
from .base import Indicator

# ECDC: "ILI and ARI consultation rates are calculated per 100 000 population, except
# for Cyprus, Luxembourg, Malta (per 100 consultations) and Finland (per 100 000
# consultations)." and "SARI rates are calculated per 100 000 hospital catchment
# population, except for Greece, Ireland, Latvia and Luxembourg (per 100 total hospital
# admissions). Data from Slovakia are based on ICU admissions."
# Per-100 values are stored multiplied by 1000, so every value is per 100,000.
_CONSULTATIONS = MappingProxyType(
    dict.fromkeys(["Cyprus", "Finland", "Luxembourg", "Malta"], "consultations")
)
_ADMISSIONS = MappingProxyType(
    dict.fromkeys(["Greece", "Ireland", "Latvia", "Luxembourg"], "admissions")
)

INDICATORS: dict[str, Indicator] = {
    "ili": Indicator(
        name="ili",
        description="Influenza-like illness consultation rate (primary care)",
        data_file=DATA_FILES["ILI_ARI"],
        ecdc_indicator="ILIconsultationrate",
        denominator_exceptions=_CONSULTATIONS,
    ),
    "ari": Indicator(
        name="ari",
        description="Acute respiratory infection consultation rate (primary care)",
        data_file=DATA_FILES["ILI_ARI"],
        ecdc_indicator="ARIconsultationrate",
        denominator_exceptions=_CONSULTATIONS,
    ),
    "sari": Indicator(
        name="sari",
        description=(
            "Severe acute respiratory infection rate (hospitals; Slovakia: ICU admissions)"
        ),
        data_file=DATA_FILES["SARI"],
        ecdc_indicator="SARIrate",
        denominator_exceptions=_ADMISSIONS,
    ),
}


def get_indicator(name: str) -> Indicator:
    """Look up an indicator by name, case-insensitively."""
    key = name.lower() if isinstance(name, str) else name
    if key not in INDICATORS:
        raise InvalidParameterError(
            f"Unknown indicator {name!r}; available: {', '.join(INDICATORS)}"
        )
    return INDICATORS[key]


__all__ = ["INDICATORS", "Indicator", "get_indicator"]
