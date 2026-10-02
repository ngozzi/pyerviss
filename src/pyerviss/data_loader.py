"""Download data files from this repository and keep them cached locally.

Each file is checked for updates at most once per CHECK_INTERVAL_SECONDS, using HTTP
ETags so unchanged files are not downloaded again. If the check fails (e.g. offline)
and a cached copy exists, the cached copy is used with a warning.

Set the PYERVISS_DATA_URL environment variable to read from another location.
"""

from __future__ import annotations

import json
import os
import time
import warnings
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from .cache import get_cache_dir
from .exceptions import DataFetchError
from .types import DATA_FILES

DATA_URL_ENV = "PYERVISS_DATA_URL"
DEFAULT_DATA_URL = "https://raw.githubusercontent.com/ngozzi/pyerviss/main/data/"
METADATA_FILE = "metadata.json"
CHECK_INTERVAL_SECONDS = 60 * 60
TIMEOUT_SECONDS = 60


# Parsed CSVs by path, with the file's modification time when parsed, so repeated
# queries skip parsing until the file changes
_frames: dict[Path, tuple[int, pd.DataFrame]] = {}


def _data_url(file_name: str) -> str:
    base = os.environ.get(DATA_URL_ENV) or DEFAULT_DATA_URL
    return base.rstrip("/") + "/" + file_name


def _state_path(path: Path) -> Path:
    return path.with_name(path.name + ".state.json")


def _read_state(path: Path) -> dict[str, Any]:
    try:
        state = json.loads(_state_path(path).read_text())
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def _write_state(path: Path, etag: str | None) -> None:
    state = {"etag": etag, "checked_at": time.time()}
    _state_path(path).write_text(json.dumps(state))


def fetch_file(file_name: str, force_refresh: bool = False) -> Path:
    """Return the path of an up-to-date cached copy of a data file.

    Args:
        file_name: File name in the repository's data/ folder, e.g. "ILIARIRates.csv".
        force_refresh: Check for updates now instead of waiting for the check interval.

    Raises:
        DataFetchError: The file could not be downloaded and no cached copy exists.
    """
    path = get_cache_dir() / file_name
    state = _read_state(path)
    if (
        path.exists()
        and not force_refresh
        and time.time() - state.get("checked_at", 0) < CHECK_INTERVAL_SECONDS
    ):
        return path

    headers = {}
    if path.exists() and state.get("etag"):
        headers["If-None-Match"] = state["etag"]
    url = _data_url(file_name)
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
        if response.status_code == 304:
            _write_state(path, state.get("etag"))
            return path
        response.raise_for_status()
    except requests.RequestException as error:
        if path.exists():
            warnings.warn(
                f"Could not check {url} for updates ({error}); using cached copy.",
                stacklevel=2,
            )
            return path
        raise DataFetchError(f"Could not download {url}: {error}") from error

    # Write to a temporary file first so an interrupted download never leaves a
    # truncated file in the cache
    partial = path.with_name(path.name + ".partial")
    partial.write_bytes(response.content)
    partial.replace(path)
    _write_state(path, response.headers.get("ETag"))
    return path


def load_csv(file_name: str, force_refresh: bool = False) -> pd.DataFrame:
    """Load a data file as a DataFrame with ECDC's columns (value as float)."""
    path = fetch_file(file_name, force_refresh=force_refresh)
    mtime = path.stat().st_mtime_ns
    cached = _frames.get(path)
    if cached is None or cached[0] != mtime:
        try:
            # Every column is text except value
            frame = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
            frame["value"] = frame["value"].astype("float64")
        except (ValueError, pd.errors.ParserError) as error:
            raise DataFetchError(
                f"Cached file {path} is unreadable ({error}); run pyerviss.clear_cache()"
            ) from error
        _frames[path] = (mtime, frame)
        return frame.copy()
    return cached[1].copy()


def get_metadata(force_refresh: bool = False) -> dict[str, Any]:
    """Return data/metadata.json: last update, record counts, date ranges and units."""
    path = fetch_file(METADATA_FILE, force_refresh=force_refresh)
    try:
        metadata: dict[str, Any] = json.loads(path.read_text())
    except ValueError as error:
        raise DataFetchError(
            f"Cached file {path} is unreadable ({error}); run pyerviss.clear_cache()"
        ) from error
    return metadata


def update_data() -> None:
    """Check all data files for updates now and download any that changed."""
    for file_name in [*DATA_FILES.values(), METADATA_FILE]:
        fetch_file(file_name, force_refresh=True)
