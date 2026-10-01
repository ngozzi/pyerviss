"""Local cache location and management.

Data files are cached in the platform's user cache directory (e.g. ~/.cache/pyerviss on
Linux). Set the PYERVISS_CACHE_DIR environment variable to use another location.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from platformdirs import user_cache_dir

from .exceptions import CacheError

CACHE_DIR_ENV = "PYERVISS_CACHE_DIR"


def get_cache_dir() -> Path:
    """Return the cache directory, creating it if needed."""
    path = Path(os.environ.get(CACHE_DIR_ENV) or user_cache_dir("pyerviss"))
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise CacheError(f"Cannot create cache directory {path}: {error}") from error
    return path


def clear_cache() -> None:
    """Delete all cached data files."""
    path = get_cache_dir()
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass
    except OSError as error:
        raise CacheError(f"Cannot clear cache directory {path}: {error}") from error
