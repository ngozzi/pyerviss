"""Type definitions and constants for PyERVISS."""

from typing import Literal

# Type aliases
Country = str
AgeGroup = Literal["0-4", "5-14", "15-64", "65+", "total"]
Season = str  # Format: "2024/25"
YearWeek = str  # Format: "2025-W03"
IndicatorName = Literal["ili", "ari", "sari"]

# Age groups, in display order
AGE_GROUPS = ["0-4", "5-14", "15-64", "65+", "total"]

# Data file names
DATA_FILES = {
    "ILI_ARI": "ILIARIRates.csv",
    "SARI": "SARIRates.csv",
}

# ISO 3166-1 alpha-2 codes for the country names used by ECDC (EU/EEA)
COUNTRY_CODES = {
    "Austria": "AT",
    "Belgium": "BE",
    "Bulgaria": "BG",
    "Croatia": "HR",
    "Cyprus": "CY",
    "Czechia": "CZ",
    "Denmark": "DK",
    "Estonia": "EE",
    "Finland": "FI",
    "France": "FR",
    "Germany": "DE",
    "Greece": "GR",
    "Hungary": "HU",
    "Iceland": "IS",
    "Ireland": "IE",
    "Italy": "IT",
    "Latvia": "LV",
    "Liechtenstein": "LI",
    "Lithuania": "LT",
    "Luxembourg": "LU",
    "Malta": "MT",
    "Netherlands": "NL",
    "Norway": "NO",
    "Poland": "PL",
    "Portugal": "PT",
    "Romania": "RO",
    "Slovakia": "SK",
    "Slovenia": "SI",
    "Spain": "ES",
    "Sweden": "SE",
}

# Other accepted spellings, mapped to ECDC names (EU institutions use "EL" for Greece)
COUNTRY_ALIASES = {
    "EL": "Greece",
    "Czech Republic": "Czechia",
    "The Netherlands": "Netherlands",
}
