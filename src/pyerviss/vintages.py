"""Data as it was published on a past date ("vintages"), from ECDC's weekly snapshots.

ECDC saves a dated copy of each file in data/snapshots/ of its repository every week it
publishes, named e.g. "2024-12-06_ILIARIRates.csv". For a date ``as_of``, the latest
snapshot dated on or before it is used, and the mirror fills in only the weeks older
than that snapshot covers, so no later revision leaks in.

Snapshots never change, so each one is downloaded on first use and cached for good. The
list of snapshots is read from the GitHub API at most once per INDEX_CHECK_SECONDS; set
the GITHUB_TOKEN environment variable to raise GitHub's rate limit (60 requests per hour
without a token).
"""

from __future__ import annotations

import json
import os
import re
import time
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from .cache import get_cache_dir
from .data_loader import TIMEOUT_SECONDS, load_csv, read_frame
from .exceptions import DataFetchError, InvalidParameterError
from .types import DATA_FILES
from .units import normalize_snapshot
from .utils import yearweek_to_date

ECDC_REPO = "EU-ECDC/Respiratory_viruses_weekly_data"
SNAPSHOTS_TREE_URL = f"https://api.github.com/repos/{ECDC_REPO}/git/trees/main:data/snapshots"
SNAPSHOT_URL = f"https://raw.githubusercontent.com/{ECDC_REPO}/main/data/snapshots/{{name}}"
INDEX_CHECK_SECONDS = 60 * 60
INDEX_FILE = "index.json"

# Warn when the snapshot used is older than this, i.e. ECDC published nothing for a while
MAX_SNAPSHOT_AGE = timedelta(days=14)
# Before the first snapshot, a week counts as published this many days after its Sunday
# (ECDC publishes on Fridays)
PUBLICATION_LAG = timedelta(days=5)

_SNAPSHOT_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_(.+)$")
# Lower-case file name -> name in DATA_FILES: ECDC's names are not consistently cased
# (2023-11-24_sentineltestsDetectionsPositivity.csv)
_CANONICAL = {name.lower(): name for name in DATA_FILES.values()}

# Columns identifying a weekly series. Virology leaves out the indicator so the
# positivity, tests and detections of a week always come from the same source.
_RATE_SERIES = ["countryname", "indicator", "age"]
_VIROLOGY_SERIES = ["countryname", "pathogen", "pathogentype", "pathogensubtype", "age"]


def _snapshot_dir() -> Path:
    path = get_cache_dir() / "snapshots"
    path.mkdir(exist_ok=True)
    return path


def _api_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _read_index(path: Path) -> dict[str, Any]:
    try:
        index = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return index if isinstance(index, dict) else {}


def _tree_entries() -> list[dict[str, Any]]:
    """Entries of ECDC's snapshot folder (path and size), from cache or the GitHub API."""
    path = _snapshot_dir() / INDEX_FILE
    index = _read_index(path)
    if time.time() - index.get("checked_at", 0) < INDEX_CHECK_SECONDS:
        return list(index.get("entries", []))
    try:
        response = requests.get(SNAPSHOTS_TREE_URL, headers=_api_headers(), timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        entries = [{"path": e["path"], "size": e.get("size")} for e in response.json()["tree"]]
    except (requests.RequestException, ValueError, KeyError, TypeError) as error:
        if "entries" in index:
            warnings.warn(
                f"Could not list ECDC snapshots ({error}); using the list from "
                f"{datetime.fromtimestamp(index['checked_at']):%Y-%m-%d %H:%M}.",
                stacklevel=3,
            )
            return list(index["entries"])
        raise DataFetchError(f"Could not list ECDC snapshots: {error}") from error
    path.write_text(json.dumps({"checked_at": time.time(), "entries": entries}))
    return entries


def snapshot_index() -> dict[str, list[tuple[date, str]]]:
    """Available snapshots per data file: {"ILIARIRates.csv": [(date, file name), ...]}.

    Lists are sorted by date. Empty files are left out.
    """
    index: dict[str, list[tuple[date, str]]] = {name: [] for name in DATA_FILES.values()}
    for entry in _tree_entries():
        match = _SNAPSHOT_NAME.match(entry["path"])
        canonical = _CANONICAL.get(match[2].lower()) if match else None
        if match is None or canonical is None or entry.get("size") == 0:
            continue
        try:
            published = date.fromisoformat(match[1])
        except ValueError:
            continue
        index[canonical].append((published, entry["path"]))
    return {name: sorted(snapshots) for name, snapshots in index.items()}


def snapshot_dates(file_name: str) -> list[date]:
    """Dates of the snapshots of a data file, oldest first."""
    return [published for published, _ in snapshot_index()[file_name]]


def fetch_snapshot(name: str) -> Path:
    """Path of a cached copy of a snapshot file, downloading it the first time."""
    path = _snapshot_dir() / name
    if path.exists():
        return path
    url = SNAPSHOT_URL.format(name=name)
    try:
        response = requests.get(url, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as error:
        raise DataFetchError(f"Could not download {url}: {error}") from error
    partial = path.with_name(path.name + ".partial")
    partial.write_bytes(response.content)
    partial.replace(path)
    return path


def parse_as_of(value: date | str) -> date:
    """Normalize an as_of date given as a date, datetime or "YYYY-MM-DD" string."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            pass
    raise InvalidParameterError(
        f"Invalid as_of {value!r}; expected a date or a string like '2024-12-06'"
    )


def load_as_of(file_name: str, as_of: date) -> pd.DataFrame:
    """Rows of a data file as published on as_of, in ECDC's layout plus a vintage column.

    vintage is the date of the snapshot a row comes from, or NaT for weeks older than
    the snapshot covers, which come from the mirror.
    """
    snapshots = [s for s in snapshot_index()[file_name] if s[0] <= as_of]
    if not snapshots:
        return _reconstruct(file_name, as_of)
    vintage, name = snapshots[-1]
    if as_of - vintage > MAX_SNAPSHOT_AGE:
        warnings.warn(
            f"The latest {file_name} snapshot on or before {as_of} is from {vintage}; "
            "ECDC published no snapshot in between.",
            stacklevel=3,
        )

    snapshot = read_frame(fetch_snapshot(name))
    snapshot = normalize_snapshot(snapshot[snapshot["value"].notna()], vintage)
    snapshot["vintage"] = pd.Timestamp(vintage)

    mirror = load_csv(file_name)
    series = _VIROLOGY_SERIES if "pathogen" in mirror.columns else _RATE_SERIES
    # Mirror rows only for weeks before the snapshot's first week of the same series (or
    # of any series, for series the snapshot lacks), so later back-fills don't leak in
    cuts = snapshot.groupby(series)["yearweek"].min().rename("_cut").reset_index()
    history = mirror.merge(cuts, on=series, how="left")
    history["_cut"] = history["_cut"].fillna(snapshot["yearweek"].min())
    history = history[history["yearweek"] < history["_cut"]].drop(columns="_cut")
    history["vintage"] = pd.NaT

    out = pd.concat([history, snapshot[history.columns]], ignore_index=True)
    out["vintage"] = out["vintage"].astype("datetime64[ns]")
    return out


def _reconstruct(file_name: str, as_of: date) -> pd.DataFrame:
    """Mirror rows for the weeks published by as_of, for dates before any snapshot."""
    warnings.warn(
        f"ECDC's {file_name} snapshots start later than {as_of}; returning the weeks "
        "published by then from current data, which includes later revisions.",
        stacklevel=3,
    )
    mirror = load_csv(file_name)
    weeks = mirror["yearweek"].unique()
    published = {w: yearweek_to_date(w) + PUBLICATION_LAG <= as_of for w in weeks}
    out = mirror[mirror["yearweek"].map(published).astype(bool)].reset_index(drop=True)
    out["vintage"] = pd.Series(pd.NaT, index=out.index, dtype="datetime64[ns]")
    return out
