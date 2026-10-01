"""Sync ILI, ARI and SARI rates from ECDC into this repository's data/ folder.

Fetches the latest ERVISS files from EU-ECDC/Respiratory_viruses_weekly_data and
merges them into the local cumulative dataset:

- rows are keyed by (countryname, yearweek, indicator, age)
- ECDC's value wins when a key exists on both sides
- rows that exist only locally are kept (never deleted)

ILI/ARI rates that ECDC publishes per 100 consultations (Cyprus, Luxembourg,
Malta) are multiplied by 1000 so every value is on a per-100,000 scale. The sync
fails if a country's values shift by orders of magnitude, which indicates a unit
change upstream rather than a revision.

Files and metadata are only rewritten when the merged data differs from what is
already on disk, so repeated runs produce no changes.

Usage:
    python scripts/sync_ecdc.py [--data-dir data] [--summary-file PATH]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ECDC_REPO = "EU-ECDC/Respiratory_viruses_weekly_data"
ECDC_BRANCH = "main"
ECDC_RAW_URL = "https://raw.githubusercontent.com/{repo}/{ref}/data/{file}"
ECDC_COMMIT_URL = "https://api.github.com/repos/{repo}/commits/{ref}"

# File name -> indicators it is expected to contain
FILES = {
    "ILIARIRates.csv": {"ILIconsultationrate", "ARIconsultationrate"},
    "SARIRates.csv": {"SARIrate"},
}

COLUMNS = ["survtype", "countryname", "yearweek", "indicator", "age", "value"]
KEY = ["countryname", "yearweek", "indicator", "age"]
SORT_ORDER = ["indicator", "countryname", "yearweek", "age"]
YEARWEEK_PATTERN = r"^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$"

TIMEOUT_SECONDS = 60

ECDC_SOURCE = f"https://github.com/{ECDC_REPO} (cumulative merge)"

# ECDC: "ILI and ARI consultation rates are calculated per 100 000 population, except
# for Cyprus, Luxembourg, Malta (per 100 consultations) and Finland (per 100 000
# consultations)." Scaling the per-100 countries by 1000 puts all values per 100,000,
# but for these four countries the denominator is consultations, not population.
PER_100_CONSULTATIONS = {"Cyprus", "Luxembourg", "Malta"}
RESCALED_INDICATORS = {"ILIconsultationrate", "ARIconsultationrate"}
RESCALE_FACTOR = 1000

_SCALED_NOTE = "ECDC publishes per 100 consultations; multiplied by 1000"
UNITS = {
    "ILIARIRates": {
        "default": "per 100,000 population",
        "exceptions": {
            "Cyprus": f"per 100,000 consultations ({_SCALED_NOTE})",
            "Finland": "per 100,000 consultations",
            "Luxembourg": f"per 100,000 consultations ({_SCALED_NOTE})",
            "Malta": f"per 100,000 consultations ({_SCALED_NOTE})",
        },
    },
    "SARIRates": {"default": "as published by ECDC (no conversion)", "exceptions": {}},
}

# A country's median value changing by more than this factor between the stored data
# and ECDC's (on the same weeks) is treated as a unit change, not a revision.
MAX_SCALE_SHIFT = 100
MIN_OVERLAP_FOR_SCALE_CHECK = 3


class ValidationError(Exception):
    """Raised when a dataset does not have the expected structure."""


@dataclass
class MergeStats:
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    local_only: int = 0

    @property
    def changed(self) -> bool:
        return self.added > 0 or self.updated > 0


def validate(df: pd.DataFrame, expected_indicators: set[str], source: str) -> pd.DataFrame:
    """Check structure and return a normalized copy (string keys, float values)."""
    if list(df.columns) != COLUMNS:
        raise ValidationError(f"{source}: expected columns {COLUMNS}, got {list(df.columns)}")
    if df.empty:
        raise ValidationError(f"{source}: no rows")

    df = df.copy()
    for col in COLUMNS[:-1]:
        if df[col].isna().any():
            raise ValidationError(f"{source}: missing values in column '{col}'")
        df[col] = df[col].astype(str).str.strip()

    bad_weeks = ~df["yearweek"].str.match(YEARWEEK_PATTERN)
    if bad_weeks.any():
        examples = df.loc[bad_weeks, "yearweek"].unique()[:5].tolist()
        raise ValidationError(f"{source}: malformed yearweek values {examples}")

    unexpected = set(df["indicator"].unique()) - expected_indicators
    if unexpected:
        raise ValidationError(f"{source}: unexpected indicators {sorted(unexpected)}")

    values = pd.to_numeric(df["value"], errors="coerce")
    if values.isna().any():
        examples = df.loc[values.isna(), "value"].unique()[:5].tolist()
        raise ValidationError(f"{source}: missing or non-numeric values {examples}")
    df["value"] = values.astype(float)

    duplicates = df.duplicated(KEY)
    if duplicates.any():
        examples = df.loc[duplicates, KEY].head(3).to_dict("records")
        raise ValidationError(f"{source}: {int(duplicates.sum())} duplicate keys, e.g. {examples}")

    return df


def normalize_units(df: pd.DataFrame) -> pd.DataFrame:
    """Convert per-100-consultation ILI/ARI rates to per 100,000."""
    mask = df["countryname"].isin(PER_100_CONSULTATIONS) & df["indicator"].isin(RESCALED_INDICATORS)
    if not mask.any():
        return df
    df = df.copy()
    # Round away float noise from the multiplication (e.g. 2.9 * 1000 = 2900.0000000000005)
    df.loc[mask, "value"] = (df.loc[mask, "value"] * RESCALE_FACTOR).round(9)
    return df


def check_scale(local: pd.DataFrame, incoming: pd.DataFrame, source: str) -> None:
    """Fail if any country/indicator's values jumped by orders of magnitude.

    Compares overlapping, non-zero rows. Revisions move values by percentages; a unit
    change (e.g. per 100 -> per 100,000) moves every value by the same large factor.
    """
    joined = local.merge(incoming, on=KEY, suffixes=("_local", "_incoming"))
    joined = joined[(joined["value_local"] > 0) & (joined["value_incoming"] > 0)]
    ratios = (joined["value_incoming"] / joined["value_local"]).groupby(
        [joined["countryname"], joined["indicator"]]
    )
    medians = ratios.median()[ratios.size() >= MIN_OVERLAP_FOR_SCALE_CHECK]
    shifted = medians[(medians > MAX_SCALE_SHIFT) | (medians < 1 / MAX_SCALE_SHIFT)]
    if not shifted.empty:
        details = ", ".join(
            f"{row.countryname} {row.indicator} (x{row.ratio:g})"
            for row in shifted.rename("ratio").reset_index().itertuples()
        )
        raise ValidationError(
            f"{source}: values changed scale, possibly a unit change upstream: {details}"
        )


def merge(local: pd.DataFrame, incoming: pd.DataFrame) -> tuple[pd.DataFrame, MergeStats]:
    """Merge incoming rows into local rows. Incoming values win; local-only rows are kept."""
    joined = local.merge(
        incoming, on=KEY, how="outer", suffixes=("_local", "_incoming"), indicator=True
    )
    in_both = joined["_merge"] == "both"
    stats = MergeStats(
        added=int((joined["_merge"] == "right_only").sum()),
        local_only=int((joined["_merge"] == "left_only").sum()),
        updated=int(
            (
                in_both
                & (
                    (joined["value_local"] != joined["value_incoming"])
                    | (joined["survtype_local"] != joined["survtype_incoming"])
                )
            ).sum()
        ),
    )
    stats.unchanged = int(in_both.sum()) - stats.updated

    merged = pd.concat([local, incoming], ignore_index=True).drop_duplicates(KEY, keep="last")
    return sort_rows(merged), stats


def sort_rows(df: pd.DataFrame) -> pd.DataFrame:
    sorted_df: pd.DataFrame = df[COLUMNS].sort_values(SORT_ORDER, ignore_index=True)
    return sorted_df


def format_value(value: float) -> str:
    """Shortest exact representation, without trailing '.0' (4345.3, 0, 12.25)."""
    return str(np.format_float_positional(value, trim="-"))


def to_csv(df: pd.DataFrame) -> str:
    out = sort_rows(df).copy()
    out["value"] = out["value"].map(format_value)
    return str(out.to_csv(index=False, lineterminator="\n"))


def read_csv(source: str | Path | io.StringIO) -> pd.DataFrame:
    # Read everything as text so validation controls the conversion
    return pd.read_csv(source, dtype=str, keep_default_na=False, na_values=[""])


def get_ecdc_commit(session: requests.Session) -> str | None:
    """Resolve the current ECDC commit so all files are fetched from the same revision."""
    try:
        response = session.get(
            ECDC_COMMIT_URL.format(repo=ECDC_REPO, ref=ECDC_BRANCH),
            headers={"Accept": "application/vnd.github.sha"},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"warning: could not resolve ECDC commit ({error}); using {ECDC_BRANCH}")
        return None
    return response.text.strip()


def fetch_ecdc_file(session: requests.Session, file_name: str, ref: str) -> pd.DataFrame:
    url = ECDC_RAW_URL.format(repo=ECDC_REPO, ref=ref, file=file_name)
    response = session.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return read_csv(io.StringIO(response.text))


def date_range(df: pd.DataFrame) -> dict[str, str]:
    return {"start": str(df["yearweek"].min()), "end": str(df["yearweek"].max())}


def update_metadata(
    path: Path,
    datasets: dict[str, pd.DataFrame],
    ecdc_commit: str | None,
    extra_source: str | None = None,
) -> None:
    """Rewrite metadata for the given datasets, keeping previously recorded sources."""
    previous = json.loads(path.read_text()) if path.exists() else {}
    sources = [
        s for s in previous.get("data_sources", []) if s.startswith("http") and s != ECDC_SOURCE
    ]
    if extra_source and extra_source not in sources:
        sources.append(extra_source)
    metadata = {
        "last_update": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "ecdc_commit": ecdc_commit,
        "records_count": {Path(name).stem: len(df) for name, df in datasets.items()},
        "date_range": {Path(name).stem: date_range(df) for name, df in datasets.items()},
        "units": UNITS,
        "data_sources": [ECDC_SOURCE, *sources],
    }
    path.write_text(json.dumps(metadata, indent=2) + "\n")


def sync(data_dir: Path, session: requests.Session) -> dict[str, MergeStats]:
    """Fetch, validate and merge all files. Writes to data_dir only if something changed."""
    ecdc_commit = get_ecdc_commit(session)
    ref = ecdc_commit or ECDC_BRANCH

    # Fetch and validate everything before writing anything
    merged: dict[str, pd.DataFrame] = {}
    stats: dict[str, MergeStats] = {}
    for file_name, indicators in FILES.items():
        incoming = validate(
            fetch_ecdc_file(session, file_name, ref), indicators, f"ECDC {file_name}"
        )
        incoming = normalize_units(incoming)
        local_path = data_dir / file_name
        if local_path.exists():
            local = validate(read_csv(local_path), indicators, f"local {file_name}")
        else:
            local = incoming.iloc[0:0]
        check_scale(local, incoming, f"ECDC {file_name}")
        merged[file_name], stats[file_name] = merge(local, incoming)

    outputs = {name: to_csv(df) for name, df in merged.items()}
    on_disk = {
        name: (data_dir / name).read_text() if (data_dir / name).exists() else None
        for name in FILES
    }
    if outputs == on_disk:
        return stats

    for name, content in outputs.items():
        (data_dir / name).write_text(content)
    update_metadata(data_dir / "metadata.json", merged, ecdc_commit)
    return stats


def summarize(stats: dict[str, MergeStats]) -> str:
    lines = ["| File | Added | Updated | Unchanged | Kept (not in ECDC) |", "|---|---|---|---|---|"]
    for name, s in stats.items():
        lines.append(f"| {name} | {s.added} | {s.updated} | {s.unchanged} | {s.local_only} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument(
        "--summary-file",
        type=Path,
        help="Append a Markdown summary here (e.g. GitHub step summary)",
    )
    args = parser.parse_args(argv)

    args.data_dir.mkdir(parents=True, exist_ok=True)
    try:
        with requests.Session() as session:
            stats = sync(args.data_dir, session)
    except (ValidationError, requests.RequestException) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    summary = summarize(stats)
    print(summary)
    if args.summary_file:
        with args.summary_file.open("a") as f:
            f.write("## ECDC data sync\n\n" + summary + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
