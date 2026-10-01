"""One-off import of historical ILI and ARI rates (2014 onwards) from RespiCast.

RespiCast's ERVISS snapshots of 2024-10-11 contain total-age ILI and ARI rates back
to 2014-W40, which ECDC no longer publishes. This script merges them into
data/ILIARIRates.csv:

- only keys missing from the master file are added; existing (ECDC) values win
- RespiCast values are already per 100,000 for every country, matching the
  master file (Cyprus, Luxembourg and Malta scaled x1000 from per 100 consultations)
- country/indicator series that are entirely zero are dropped as missing data

Re-running is a no-op once the rows are in.

Usage:
    python scripts/import_respicast.py [--data-dir data]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import pandas as pd
import requests
from sync_ecdc import (
    COLUMNS,
    FILES,
    TIMEOUT_SECONDS,
    ValidationError,
    check_scale,
    merge,
    read_csv,
    to_csv,
    update_metadata,
    validate,
)

RESPICAST_REPO = "european-modelling-hubs/RespiCast-SyndromicIndicators"
RESPICAST_URL = "https://raw.githubusercontent.com/{repo}/main/target-data/ERVISS/snapshots/{file}"
SNAPSHOT_FILES = {
    "ILIconsultationrate": "2024-10-11-ILI_incidence.csv",
    "ARIconsultationrate": "2024-10-11-ARI_incidence.csv",
}
TARGETS = {"ILIconsultationrate": "ILI incidence", "ARIconsultationrate": "ARI incidence"}
RESPICAST_COLUMNS = ["target", "location", "truth_date", "year_week", "value"]
RESPICAST_SOURCE = (
    f"https://github.com/{RESPICAST_REPO} (one-off import of 2024-10-11 ERVISS snapshots: "
    "ILI and ARI, total age, from 2014-W40)"
)

MASTER_FILE = "ILIARIRates.csv"
SURVTYPE = "primary care syndromic"
AGE = "total"

COUNTRIES = {
    "AT": "Austria",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "EE": "Estonia",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "GR": "Greece",
    "HR": "Croatia",
    "HU": "Hungary",
    "IE": "Ireland",
    "IS": "Iceland",
    "IT": "Italy",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "MT": "Malta",
    "NL": "Netherlands",
    "NO": "Norway",
    "PL": "Poland",
    "PT": "Portugal",
    "RO": "Romania",
    "SE": "Sweden",
    "SI": "Slovenia",
    "SK": "Slovakia",
}


def to_master_format(raw: pd.DataFrame, indicator: str) -> pd.DataFrame:
    """Convert a RespiCast snapshot to the master file's columns (values stay strings)."""
    source = SNAPSHOT_FILES[indicator]
    if list(raw.columns) != RESPICAST_COLUMNS:
        raise ValidationError(f"{source}: expected columns {RESPICAST_COLUMNS}")
    targets = set(raw["target"].unique())
    if targets != {TARGETS[indicator]}:
        raise ValidationError(f"{source}: unexpected targets {sorted(targets)}")
    unknown = set(raw["location"].unique()) - set(COUNTRIES)
    if unknown:
        raise ValidationError(f"{source}: unknown location codes {sorted(unknown)}")

    out = pd.DataFrame(
        {
            "survtype": SURVTYPE,
            "countryname": raw["location"].map(COUNTRIES),
            "yearweek": raw["year_week"],
            "indicator": indicator,
            "age": AGE,
            "value": raw["value"],
        }
    )
    return out[COLUMNS]


def drop_all_zero_series(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Drop country/indicator series whose values are all zero (missing data coded as 0)."""
    all_zero = df.groupby(["countryname", "indicator"])["value"].transform(lambda v: (v == 0).all())
    counts = df[all_zero].groupby(["countryname", "indicator"]).size().rename("rows")
    dropped = [
        f"{row.countryname} {row.indicator} ({row.rows} rows)"
        for row in counts.reset_index().itertuples()
    ]
    return df[~all_zero].reset_index(drop=True), dropped


def fetch_snapshot(session: requests.Session, indicator: str) -> pd.DataFrame:
    url = RESPICAST_URL.format(repo=RESPICAST_REPO, file=SNAPSHOT_FILES[indicator])
    response = session.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return read_csv(io.StringIO(response.text))


def import_respicast(data_dir: Path, session: requests.Session) -> int:
    """Merge RespiCast history into the master file. Returns the number of rows added."""
    indicators = FILES[MASTER_FILE]
    master_path = data_dir / MASTER_FILE
    master = validate(read_csv(master_path), indicators, f"local {MASTER_FILE}")

    history = pd.concat(
        [to_master_format(fetch_snapshot(session, ind), ind) for ind in SNAPSHOT_FILES],
        ignore_index=True,
    )
    history = validate(history, indicators, "RespiCast")
    history, dropped = drop_all_zero_series(history)
    for series in dropped:
        print(f"dropped all-zero series: {series}")

    # Same units as the master on overlapping weeks, then fill gaps only (master wins)
    check_scale(master, history, "RespiCast")
    merged, stats = merge(history, master)
    added = stats.local_only
    if added == 0:
        return 0

    master_path.write_text(to_csv(merged))
    metadata_path = data_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    datasets = {name: validate(read_csv(data_dir / name), FILES[name], name) for name in FILES}
    update_metadata(
        metadata_path, datasets, metadata.get("ecdc_commit"), extra_source=RESPICAST_SOURCE
    )
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args(argv)

    try:
        with requests.Session() as session:
            added = import_respicast(args.data_dir, session)
    except (ValidationError, requests.RequestException) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"added {added} rows to {args.data_dir / MASTER_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
