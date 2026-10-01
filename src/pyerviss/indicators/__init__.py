"""Indicator registry.

To add an indicator, register an ``Indicator`` here and make sure the sync script
mirrors its data file.
"""

from __future__ import annotations

from ..exceptions import InvalidParameterError
from ..types import DATA_FILES
from .base import Indicator

# ECDC: "ILI and ARI consultation rates are calculated per 100 000 population, except
# for Cyprus, Luxembourg, Malta (per 100 consultations) and Finland (per 100 000
# consultations)." The per-100 values are stored multiplied by 1000.
_CONSULTATION_COUNTRIES = frozenset({"Cyprus", "Finland", "Luxembourg", "Malta"})

INDICATORS: dict[str, Indicator] = {
    "ili": Indicator(
        name="ili",
        description="Influenza-like illness consultation rate (primary care)",
        data_file=DATA_FILES["ILI_ARI"],
        ecdc_indicator="ILIconsultationrate",
        consultation_countries=_CONSULTATION_COUNTRIES,
    ),
    "ari": Indicator(
        name="ari",
        description="Acute respiratory infection consultation rate (primary care)",
        data_file=DATA_FILES["ILI_ARI"],
        ecdc_indicator="ARIconsultationrate",
        consultation_countries=_CONSULTATION_COUNTRIES,
    ),
    "sari": Indicator(
        name="sari",
        description="Severe acute respiratory infection rate (hospitals)",
        data_file=DATA_FILES["SARI"],
        ecdc_indicator="SARIrate",
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
