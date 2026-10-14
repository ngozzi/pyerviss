"""One-off import of history ECDC has trimmed from its current files.

ECDC's files only cover a rolling window of recent seasons, and older weeks are dropped
from time to time (e.g. primary care virology went from 2014-W40 to 2020-W25 in
October 2024). ECDC never rewrote its git history, so every past version of each file
is still available. This script reads each file at every ECDC commit that changed it
and merges the rows missing from the master files in data/:

- only weeks older than ECDC's current window are imported; rows ECDC removed within
  its window (retracted series, dropped categories such as "Influenza A / total") are
  left out
- a row's value comes from the most recent ECDC commit that still has it
- only keys missing from the master file are added; existing values win
- each version is validated and unit-normalized like the daily sync, and scale-checked
  against the master and against the newer versions it overlaps
- until 2025-10-24 ECDC published Greece and Latvia SARI rates already per 100,000
  hospital admissions (exactly 1000x the per-100 values it publishes since), so older
  versions are not rescaled for them
- rate series that are entirely zero in the imported history are dropped as missing
  data, as in import_respicast.py (Malta ARI 2014-W41 to 2015-W20)

Downloads are cached in --cache-dir, so an interrupted run resumes where it stopped.
Re-running is a no-op once the rows are in.

Usage:
    python scripts/import_ecdc_history.py [--data-dir data] [--cache-dir PATH]
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import sys
from collections.abc import Iterable
from pathlib import Path

import pandas as pd
import requests
from import_respicast import drop_all_zero_series
from sync_ecdc import (
    ECDC_RAW_URL,
    ECDC_REPO,
    FILES,
    TIMEOUT_SECONDS,
    FileSpec,
    ValidationError,
    check_scale,
    merge,
    normalize_units,
    read_csv,
    to_csv,
    update_metadata,
    validate,
)

ECDC_COMMITS_URL = "https://api.github.com/repos/{repo}/commits"
PAGE_SIZE = 100
HISTORY_SOURCE = (
    f"https://github.com/{ECDC_REPO} git history (one-off import of weeks ECDC has since "
    "trimmed: ILI/ARI by age group from 2014-W40, primary care virology from 2014-W25, "
    "SARI rates and virology from 2020-W40)"
)

# First ECDC commit (2025-10-24) publishing these rates per 100 admissions; versions
# older than it already have them per 100,000
UNIT_SWITCH_COMMIT = "b7a19c70856c95a39e9b1f7563e317f1ffccac33"
PER_100K_BEFORE_SWITCH = {"SARIrate": {"Greece", "Latvia"}}

# Files where a series of zeros means missing data; virology zeros are real counts
RATE_FILES = {"ILIARIRates.csv", "SARIRates.csv"}


def _api_headers() -> dict[str, str]:
    # Unauthenticated requests are limited to 60 per hour; a token raises the limit
    token = os.environ.get("GITHUB_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def list_commits(session: requests.Session, file_name: str) -> list[str]:
    """SHAs of the ECDC commits that changed data/<file_name>, newest first."""
    shas: list[str] = []
    page = 1
    while True:
        response = session.get(
            ECDC_COMMITS_URL.format(repo=ECDC_REPO),
            params={"path": f"data/{file_name}", "per_page": PAGE_SIZE, "page": page},
            headers=_api_headers(),
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        batch = [commit["sha"] for commit in response.json()]
        if not batch:
            return shas
        shas.extend(batch)
        page += 1


def fetch_version(
    session: requests.Session, file_name: str, sha: str, cache_dir: Path
) -> pd.DataFrame:
    """Read data/<file_name> as of an ECDC commit, downloading it once into cache_dir."""
    path = cache_dir / sha / (file_name + ".gz")
    if not path.exists():
        url = ECDC_RAW_URL.format(repo=ECDC_REPO, ref=sha, file=file_name)
        response = session.get(url, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(gzip.compress(response.content))
        tmp.replace(path)
    return read_csv(io.StringIO(gzip.decompress(path.read_bytes()).decode()))


def missing_rows(df: pd.DataFrame, present: pd.DataFrame, spec: FileSpec) -> pd.DataFrame:
    """Rows of df whose key is not in present."""
    key = list(spec.key)
    joined = df.merge(present[key], on=key, how="left", indicator=True)
    result: pd.DataFrame = df[(joined["_merge"] == "left_only").to_numpy()]
    return result


def normalize_version(df: pd.DataFrame, before_switch: bool) -> pd.DataFrame:
    """Unit-normalize one version, leaving rates it already has per 100,000 unchanged."""
    if not before_switch:
        return normalize_units(df)
    exempt = pd.Series(False, index=df.index)
    for indicator, countries in PER_100K_BEFORE_SWITCH.items():
        exempt |= (df["indicator"] == indicator) & df["countryname"].isin(countries)
    return pd.concat([normalize_units(df[~exempt]), df[exempt]])


def collect_history(
    versions: Iterable[tuple[str, pd.DataFrame]],
    master: pd.DataFrame,
    spec: FileSpec,
    file_name: str,
) -> pd.DataFrame:
    """Rows trimmed from ECDC's window, each taken from the newest version that has it.

    versions yields (sha, raw frame) pairs, newest first; the first one sets the window.
    """
    history = master.iloc[0:0]
    window_start: str | None = None
    before_switch = False
    for sha, raw in versions:
        source = f"ECDC {file_name} at {sha[:10]}"
        version = normalize_version(validate(raw, spec, source), before_switch)
        check_scale(master, version, spec, source)
        check_scale(history, version, spec, source)
        if window_start is None:
            window_start = str(version["yearweek"].min())
        trimmed = version[version["yearweek"] < window_start]
        new = missing_rows(missing_rows(trimmed, master, spec), history, spec)
        history = pd.concat([history, new], ignore_index=True)
        before_switch = before_switch or sha == UNIT_SWITCH_COMMIT
    return history


def import_history(
    data_dir: Path,
    session: requests.Session,
    cache_dir: Path,
    file_names: Iterable[str] = FILES,
) -> dict[str, int]:
    """Merge trimmed history into the master files. Returns rows added per file."""
    # Collect and validate everything before writing anything
    merged: dict[str, pd.DataFrame] = {}
    added: dict[str, int] = {}
    for file_name in file_names:
        spec = FILES[file_name]
        master = validate(read_csv(data_dir / file_name), spec, f"local {file_name}")
        shas = list_commits(session, file_name)
        print(f"{file_name}: {len(shas)} ECDC versions")

        versions = ((sha, fetch_version(session, file_name, sha, cache_dir)) for sha in shas)
        history = collect_history(versions, master, spec, file_name)
        if file_name in RATE_FILES and not history.empty:
            history, dropped = drop_all_zero_series(history)
            for series in dropped:
                print(f"dropped all-zero series: {series}")
        merged[file_name], stats = merge(history, master, spec)
        added[file_name] = stats.local_only

    changed = {name: df for name, df in merged.items() if added[name] > 0}
    if not changed:
        return added

    for name, df in changed.items():
        (data_dir / name).write_text(to_csv(df, FILES[name]))
    metadata_path = data_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    datasets = {
        name: validate(read_csv(data_dir / name), spec, name)
        for name, spec in FILES.items()
        if (data_dir / name).exists()
    }
    update_metadata(
        metadata_path, datasets, metadata.get("ecdc_commit"), extra_source=HISTORY_SOURCE
    )
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(".ecdc-history-cache"),
        help="Where downloaded file versions are kept",
    )
    parser.add_argument(
        "--files", nargs="+", choices=list(FILES), default=list(FILES), help="Files to import"
    )
    args = parser.parse_args(argv)

    try:
        with requests.Session() as session:
            added = import_history(args.data_dir, session, args.cache_dir, args.files)
    except (ValidationError, requests.RequestException) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    for name, count in added.items():
        print(f"added {count} rows to {args.data_dir / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
