"""Unofficial Python API for ERVISS (European Respiratory Virus Surveillance Summary) data.

Not affiliated with or endorsed by ECDC.
"""

from importlib.metadata import PackageNotFoundError, version

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

# The version is defined once, in pyproject.toml, and read from the installed package
try:
    __version__ = version("pyerviss")
except PackageNotFoundError:  # running from a source tree without installing
    __version__ = "0+unknown"

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
