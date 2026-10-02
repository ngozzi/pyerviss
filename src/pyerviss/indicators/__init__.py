"""Indicator registry.

To add a rate indicator, register an ``Indicator`` here and make sure the sync script
mirrors its data file. Positivity (virology) is described by ``POSITIVITY_FILES`` and
``PATHOGENS``.
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
    dict.fromkeys(["Cyprus", "Finland", "Luxembourg", "Malta"], "per 100,000 consultations")
)
_ADMISSIONS = MappingProxyType(
    dict.fromkeys(["Greece", "Ireland", "Latvia", "Luxembourg"], "per 100,000 hospital admissions")
)

INDICATORS: dict[str, Indicator] = {
    "ili": Indicator(
        name="ili",
        description="Influenza-like illness consultation rate (primary care)",
        data_file=DATA_FILES["ILI_ARI"],
        ecdc_indicator="ILIconsultationrate",
        unit_exceptions=_CONSULTATIONS,
    ),
    "ari": Indicator(
        name="ari",
        description="Acute respiratory infection consultation rate (primary care)",
        data_file=DATA_FILES["ILI_ARI"],
        ecdc_indicator="ARIconsultationrate",
        unit_exceptions=_CONSULTATIONS,
    ),
    "sari": Indicator(
        name="sari",
        description=(
            "Severe acute respiratory infection rate (hospitals; Slovakia: ICU admissions)"
        ),
        data_file=DATA_FILES["SARI"],
        ecdc_indicator="SARIrate",
        unit_exceptions=_ADMISSIONS,
    ),
}

# Positivity: setting -> virology data file. Primary care samples come from patients
# with ILI and/or ARI at sentinel GPs; hospital samples from SARI patients.
POSITIVITY_FILES = {
    "primary care": DATA_FILES["SENTINEL_VIROLOGY"],
    "hospital": DATA_FILES["SARI_VIROLOGY"],
}

# Pathogens with published positivity: API name -> name in ECDC's files
PATHOGENS = {"influenza": "Influenza", "rsv": "RSV", "sars-cov-2": "SARS-CoV-2"}
PATHOGEN_ALIASES = {"flu": "influenza", "covid": "sars-cov-2", "covid-19": "sars-cov-2"}


def get_indicator(name: str) -> Indicator:
    """Look up an indicator by name, case-insensitively."""
    key = name.lower() if isinstance(name, str) else name
    if key not in INDICATORS:
        raise InvalidParameterError(
            f"Unknown indicator {name!r}; available: {', '.join(INDICATORS)}"
        )
    return INDICATORS[key]


__all__ = [
    "INDICATORS",
    "PATHOGENS",
    "PATHOGEN_ALIASES",
    "POSITIVITY_FILES",
    "Indicator",
    "get_indicator",
]
