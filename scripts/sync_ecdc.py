"""Sync ERVISS data from ECDC into this repository's data/ folder.

Fetches the latest ERVISS files from EU-ECDC/Respiratory_viruses_weekly_data (ILI, ARI
and SARI rates; primary care and SARI virology) and merges them into the local
cumulative dataset:

- rows are keyed by every column except survtype and value (for rates: countryname,
  yearweek, indicator, age; virology adds pathogen, pathogentype, pathogensubtype)
- ECDC's value wins when a key exists on both sides
- rows that exist only locally are kept (never deleted)

Rates that ECDC publishes per 100 consultations (ILI/ARI: Cyprus, Luxembourg, Malta)
or per 100 hospital admissions (SARI: Greece, Ireland, Latvia, Luxembourg) are
multiplied by 1000 so every value is per 100,000 of its denominator. The sync
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


@dataclass(frozen=True)
class FileSpec:
    """Layout of one ECDC data file.

    Attributes:
        columns: Expected columns, in order; the last one is "value".
        key: Columns identifying a row (everything except survtype and value).
        indicators: Values the "indicator" column may take.
    """

    columns: tuple[str, ...]
    key: tuple[str, ...]
    indicators: frozenset[str]

    @property
    def sort_order(self) -> list[str]:
        # Indicator first, then the rest of the key in column order
        return ["indicator", *[c for c in self.key if c != "indicator"]]

    @property
    def series(self) -> list[str]:
        """Columns identifying a weekly series (the key without the week)."""
        return [c for c in self.key if c != "yearweek"]


_RATE_COLUMNS = ("survtype", "countryname", "yearweek", "indicator", "age", "value")
_RATE_KEY = ("countryname", "yearweek", "indicator", "age")
_VIROLOGY_COLUMNS = (
    "survtype",
    "countryname",
    "yearweek",
    "pathogen",
    "pathogentype",
    "pathogensubtype",
    "indicator",
    "age",
    "value",
)
_VIROLOGY_KEY = (
    "countryname",
    "yearweek",
    "pathogen",
    "pathogentype",
    "pathogensubtype",
    "indicator",
    "age",
)
_VIROLOGY_INDICATORS = frozenset({"tests", "detections", "positivity"})

FILES = {
    "ILIARIRates.csv": FileSpec(
        _RATE_COLUMNS, _RATE_KEY, frozenset({"ILIconsultationrate", "ARIconsultationrate"})
    ),
    "SARIRates.csv": FileSpec(_RATE_COLUMNS, _RATE_KEY, frozenset({"SARIrate"})),
    # Primary care sentinel and SARI (hospital) virology: tests, detections, positivity
    "sentinelTestsDetectionsPositivity.csv": FileSpec(
        _VIROLOGY_COLUMNS, _VIROLOGY_KEY, _VIROLOGY_INDICATORS
    ),
    "SARITestsDetectionsPositivity.csv": FileSpec(
        _VIROLOGY_COLUMNS, _VIROLOGY_KEY, _VIROLOGY_INDICATORS
    ),
}

YEARWEEK_PATTERN = r"^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$"

TIMEOUT_SECONDS = 60

ECDC_SOURCE = f"https://github.com/{ECDC_REPO} (cumulative merge)"

# ECDC: "ILI and ARI consultation rates are calculated per 100 000 population, except
# for Cyprus, Luxembourg, Malta (per 100 consultations) and Finland (per 100 000
# consultations)." and "SARI rates are calculated per 100 000 hospital catchment
# population, except for Greece, Ireland, Latvia and Luxembourg (per 100 total hospital
# admissions). Data from Slovakia are based on ICU admissions."
# Multiplying the per-100 countries by 1000 puts every value per 100,000 of its
# denominator; the denominator itself still differs by country.
_PER_100_CONSULTATIONS = {"Cyprus", "Luxembourg", "Malta"}
_PER_100_ADMISSIONS = {"Greece", "Ireland", "Latvia", "Luxembourg"}
PER_100_COUNTRIES = {
    "ILIconsultationrate": _PER_100_CONSULTATIONS,
    "ARIconsultationrate": _PER_100_CONSULTATIONS,
    "SARIrate": _PER_100_ADMISSIONS,
}
RESCALE_FACTOR = 1000

_CONSULTATIONS = (
    "per 100,000 consultations (ECDC publishes per 100 consultations; multiplied by 1000)"
)
_ADMISSIONS = (
    "per 100,000 hospital admissions "
    "(ECDC publishes per 100 total hospital admissions; multiplied by 1000)"
)
UNITS = {
    "ILIARIRates": {
        "default": "per 100,000 population",
        "exceptions": {
            "Cyprus": _CONSULTATIONS,
            "Finland": "per 100,000 consultations",
            "Luxembourg": _CONSULTATIONS,
            "Malta": _CONSULTATIONS,
        },
    },
    "SARIRates": {
        "default": "per 100,000 hospital catchment population",
        "exceptions": {
            "Greece": _ADMISSIONS,
            "Ireland": _ADMISSIONS,
            "Latvia": _ADMISSIONS,
            "Luxembourg": _ADMISSIONS,
            "Slovakia": "per 100,000 hospital catchment population (ICU admissions only)",
        },
    },
    "sentinelTestsDetectionsPositivity": {
        "positivity": "%",
        "tests": "count",
        "detections": "count",
    },
    "SARITestsDetectionsPositivity": {"positivity": "%", "tests": "count", "detections": "count"},
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


def validate(df: pd.DataFrame, spec: FileSpec, source: str) -> pd.DataFrame:
    """Check structure and return a normalized copy (string keys, float values)."""
    columns = list(spec.columns)
    if list(df.columns) != columns:
        raise ValidationError(f"{source}: expected columns {columns}, got {list(df.columns)}")
    if df.empty:
        raise ValidationError(f"{source}: no rows")

    df = df.copy()
    for col in columns[:-1]:
        if df[col].isna().any():
            raise ValidationError(f"{source}: missing values in column '{col}'")
        df[col] = df[col].astype(str).str.strip()

    bad_weeks = ~df["yearweek"].str.match(YEARWEEK_PATTERN)
    if bad_weeks.any():
        examples = df.loc[bad_weeks, "yearweek"].unique()[:5].tolist()
        raise ValidationError(f"{source}: malformed yearweek values {examples}")

    unexpected = set(df["indicator"].unique()) - spec.indicators
    if unexpected:
        raise ValidationError(f"{source}: unexpected indicators {sorted(unexpected)}")

    values = pd.to_numeric(df["value"], errors="coerce")
    if values.isna().any():
        examples = df.loc[values.isna(), "value"].unique()[:5].tolist()
        raise ValidationError(f"{source}: missing or non-numeric values {examples}")
    df["value"] = values.astype(float)

    key = list(spec.key)
    duplicates = df.duplicated(key)
    if duplicates.any():
        examples = df.loc[duplicates, key].head(3).to_dict("records")
        raise ValidationError(f"{source}: {int(duplicates.sum())} duplicate keys, e.g. {examples}")

    return df


def normalize_units(df: pd.DataFrame) -> pd.DataFrame:
    """Convert rates ECDC publishes per 100 (consultations/admissions) to per 100,000."""
    mask = pd.Series(False, index=df.index)
    for indicator, countries in PER_100_COUNTRIES.items():
        mask |= (df["indicator"] == indicator) & df["countryname"].isin(countries)
    if not mask.any():
        return df
    df = df.copy()
    # Round away float noise from the multiplication (e.g. 2.9 * 1000 = 2900.0000000000005)
    df.loc[mask, "value"] = (df.loc[mask, "value"] * RESCALE_FACTOR).round(9)
    return df


def check_scale(local: pd.DataFrame, incoming: pd.DataFrame, spec: FileSpec, source: str) -> None:
    """Fail if any series' values jumped by orders of magnitude.

    Compares overlapping, non-zero rows of each series (e.g. one country, indicator and
    age group). Revisions move values by percentages; a unit change (e.g. per 100 ->
    per 100,000) moves every value by the same large factor.
    """
    joined = local.merge(incoming, on=list(spec.key), suffixes=("_local", "_incoming"))
    joined = joined[(joined["value_local"] > 0) & (joined["value_incoming"] > 0)]
    ratios = (joined["value_incoming"] / joined["value_local"]).groupby(
        [joined[c] for c in spec.series]
    )
    medians = ratios.median()[ratios.size() >= MIN_OVERLAP_FOR_SCALE_CHECK]
    shifted = medians[(medians > MAX_SCALE_SHIFT) | (medians < 1 / MAX_SCALE_SHIFT)]
    if not shifted.empty:
        frame = shifted.rename("ratio").reset_index()
        details = ", ".join(
            " ".join(str(row[c]) for c in spec.series) + f" (x{row['ratio']:g})"
            for _, row in frame.iterrows()
        )
        raise ValidationError(
            f"{source}: values changed scale, possibly a unit change upstream: {details}"
        )


def merge(
    local: pd.DataFrame, incoming: pd.DataFrame, spec: FileSpec
) -> tuple[pd.DataFrame, MergeStats]:
    """Merge incoming rows into local rows. Incoming values win; local-only rows are kept."""
    key = list(spec.key)
    joined = local.merge(
        incoming, on=key, how="outer", suffixes=("_local", "_incoming"), indicator=True
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

    merged = pd.concat([local, incoming], ignore_index=True).drop_duplicates(key, keep="last")
    return sort_rows(merged, spec), stats


def sort_rows(df: pd.DataFrame, spec: FileSpec) -> pd.DataFrame:
    sorted_df: pd.DataFrame = df[list(spec.columns)].sort_values(spec.sort_order, ignore_index=True)
    return sorted_df


def format_value(value: float) -> str:
    """Shortest exact representation, without trailing '.0' (4345.3, 0, 12.25)."""
    return str(np.format_float_positional(value, trim="-"))


def to_csv(df: pd.DataFrame, spec: FileSpec) -> str:
    out = sort_rows(df, spec).copy()
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
    for file_name, spec in FILES.items():
        incoming = validate(fetch_ecdc_file(session, file_name, ref), spec, f"ECDC {file_name}")
        incoming = normalize_units(incoming)
        local_path = data_dir / file_name
        if local_path.exists():
            local = validate(read_csv(local_path), spec, f"local {file_name}")
        else:
            local = incoming.iloc[0:0]
        check_scale(local, incoming, spec, f"ECDC {file_name}")
        merged[file_name], stats[file_name] = merge(local, incoming, spec)

    outputs = {name: to_csv(df, FILES[name]) for name, df in merged.items()}
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
