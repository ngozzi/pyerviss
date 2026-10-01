"""Unofficial Python API for ERVISS (European Respiratory Virus Surveillance Summary) data.

Not affiliated with or endorsed by ECDC.
"""

from .api import (
    clear_cache,
    coverage,
    get_ari,
    get_data,
    get_ili,
    get_sari,
    latest_week,
    list_countries,
    list_seasons,
    update_data,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "clear_cache",
    "coverage",
    "get_ari",
    "get_data",
    "get_ili",
    "get_sari",
    "latest_week",
    "list_countries",
    "list_seasons",
    "update_data",
]
