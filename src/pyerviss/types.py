"""Type definitions and constants for PyERVISS."""

from typing import Literal

# Type aliases
Country = str
AgeGroup = Literal["0-4", "5-14", "15-64", "65+", "total"]
Season = str  # Format: "2024/25"
YearWeek = str  # Format: "2025-W03"
Indicator = Literal["ILIconsultationrate", "ARIconsultationrate", "SARIrate"]

# Countries available for ILI/ARI data, as of ECDC data for 2026-W38.
# Reporting countries change over time; once data loading is implemented,
# list_countries() should derive these from the data instead.
COUNTRIES_ILI_ARI = [
    "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia",
    "Denmark", "Estonia", "Finland", "France", "Germany", "Greece",
    "Hungary", "Iceland", "Ireland", "Italy", "Latvia", "Lithuania",
    "Luxembourg", "Malta", "Netherlands", "Norway", "Poland", "Portugal",
    "Romania", "Slovakia", "Slovenia", "Spain",
]

# Countries available for SARI data, as of ECDC data for 2026-W38
COUNTRIES_SARI = [
    "Austria", "Belgium", "Croatia", "Cyprus", "Estonia", "Germany",
    "Greece", "Iceland", "Ireland", "Latvia", "Lithuania", "Luxembourg",
    "Malta", "Romania", "Slovakia", "Spain",
]

# Age groups
AGE_GROUPS = ["0-4", "5-14", "15-64", "65+", "total"]

# Data file names
DATA_FILES = {
    "ILI_ARI": "ILIARIRates.csv",
    "SARI": "SARIRates.csv",
}
