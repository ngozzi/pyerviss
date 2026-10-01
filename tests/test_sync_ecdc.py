"""Tests for scripts/sync_ecdc.py."""

import io
import json

import pandas as pd
import pytest
import requests
import sync_ecdc
from sync_ecdc import (
    ECDC_SOURCE,
    KEY,
    ValidationError,
    check_scale,
    merge,
    normalize_units,
    read_csv,
    sync,
    to_csv,
    update_metadata,
    validate,
)

HEADER = "survtype,countryname,yearweek,indicator,age,value\n"
ILI_ARI = {"ILIconsultationrate", "ARIconsultationrate"}


def ili_csv(*rows: str) -> str:
    return HEADER + "".join(f"primary care syndromic,{row}\n" for row in rows)


def sari_csv(*rows: str) -> str:
    return HEADER + "".join(f"SARI syndromic,{row}\n" for row in rows)


def frame(text: str, indicators: set[str] = ILI_ARI) -> pd.DataFrame:
    return validate(read_csv(io.StringIO(text)), indicators, "test")


class FakeResponse:
    def __init__(self, text: str, status: int = 200):
        self.text = text
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class FakeSession:
    """Serves ECDC files by name; records requested URLs."""

    def __init__(self, files: dict[str, str], commit: str | None = "abc123"):
        self.files = files
        self.commit = commit
        self.urls: list[str] = []

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.urls.append(url)
        if "api.github.com" in url:
            if self.commit is None:
                raise requests.ConnectionError("offline")
            return FakeResponse(self.commit)
        name = url.rsplit("/", 1)[-1]
        if name not in self.files:
            return FakeResponse("not found", 404)
        return FakeResponse(self.files[name])


# --- validate ---------------------------------------------------------------


def test_validate_accepts_valid_data():
    df = frame(ili_csv("Austria,2025-W03,ILIconsultationrate,0-4,857.6"))
    assert df["value"].tolist() == [857.6]


@pytest.mark.parametrize(
    "text, message",
    [
        ("a,b\n1,2\n", "expected columns"),
        (HEADER, "no rows"),
        (ili_csv("Austria,2025-3,ILIconsultationrate,0-4,1"), "malformed yearweek"),
        (ili_csv("Austria,2025-W54,ILIconsultationrate,0-4,1"), "malformed yearweek"),
        (ili_csv("Austria,2025-W03,SARIrate,0-4,1"), "unexpected indicators"),
        (ili_csv("Austria,2025-W03,ILIconsultationrate,0-4,"), "non-numeric"),
        (ili_csv("Austria,2025-W03,ILIconsultationrate,0-4,n/a"), "non-numeric"),
        (ili_csv(",2025-W03,ILIconsultationrate,0-4,1"), "missing values in column"),
        (
            ili_csv(
                "Austria,2025-W03,ILIconsultationrate,0-4,1",
                "Austria,2025-W03,ILIconsultationrate,0-4,2",
            ),
            "duplicate keys",
        ),
    ],
)
def test_validate_rejects_bad_data(text, message):
    with pytest.raises(ValidationError, match=message):
        frame(text)


# --- merge ------------------------------------------------------------------


def test_merge_updates_adds_and_keeps_local_only_rows():
    local = frame(
        ili_csv(
            "Austria,2015-W01,ILIconsultationrate,total,10",  # not in ECDC anymore
            "Austria,2025-W03,ILIconsultationrate,total,20",  # revised by ECDC
            "Austria,2025-W04,ILIconsultationrate,total,30",  # unchanged
        )
    )
    incoming = frame(
        ili_csv(
            "Austria,2025-W03,ILIconsultationrate,total,21.5",
            "Austria,2025-W04,ILIconsultationrate,total,30",
            "Austria,2025-W05,ILIconsultationrate,total,40",  # new week
        )
    )

    merged, stats = merge(local, incoming)

    values = merged.set_index("yearweek")["value"].to_dict()
    assert values == {"2015-W01": 10, "2025-W03": 21.5, "2025-W04": 30, "2025-W05": 40}
    assert (stats.added, stats.updated, stats.unchanged, stats.local_only) == (1, 1, 1, 1)
    assert stats.changed


def test_merge_never_drops_rows():
    local = frame(
        ili_csv(*[f"Austria,2015-W{w:02d},ARIconsultationrate,0-4,{w}" for w in range(1, 11)])
    )
    incoming = frame(ili_csv("Austria,2025-W01,ARIconsultationrate,0-4,1"))

    merged, _ = merge(local, incoming)

    local_keys = set(map(tuple, local[KEY].values))
    merged_keys = set(map(tuple, merged[KEY].values))
    assert local_keys <= merged_keys
    assert len(merged) == 11


def test_merge_identical_data_reports_no_change():
    data = frame(ili_csv("Austria,2025-W03,ILIconsultationrate,total,20"))
    _, stats = merge(data, data.copy())
    assert not stats.changed
    assert stats.unchanged == 1


def test_merge_into_empty_local():
    incoming = frame(ili_csv("Austria,2025-W03,ILIconsultationrate,total,20"))
    merged, stats = merge(incoming.iloc[0:0], incoming)
    assert len(merged) == 1
    assert stats.added == 1


# --- units ------------------------------------------------------------------


def test_normalize_units_scales_per_100_consultation_countries():
    df = frame(
        ili_csv(
            "Malta,2025-W03,ILIconsultationrate,total,5.15",
            "Luxembourg,2025-W03,ARIconsultationrate,0-4,2.9",
            "Cyprus,2025-W03,ARIconsultationrate,total,13.1",
            "Finland,2025-W03,ILIconsultationrate,total,8.8",
            "Austria,2025-W03,ILIconsultationrate,total,2338",
        )
    )

    values = normalize_units(df).set_index("countryname")["value"].to_dict()

    # Exact results, no float noise (2.9 * 1000 == 2900.0000000000005)
    assert values == {
        "Malta": 5150,
        "Luxembourg": 2900,
        "Cyprus": 13100,
        "Finland": 8.8,
        "Austria": 2338,
    }
    assert "Luxembourg,2025-W03,ARIconsultationrate,0-4,2900\n" in to_csv(normalize_units(df))


def test_normalize_units_scales_per_100_admission_sari_countries():
    df = frame(
        sari_csv(
            "Ireland,2025-W03,SARIrate,total,3.5",
            "Luxembourg,2025-W03,SARIrate,65+,1.3",
            "Malta,2025-W03,SARIrate,total,8.1",  # per catchment population: unchanged
            "Slovakia,2025-W03,SARIrate,total,0.1",  # ICU-based, same unit: unchanged
        ),
        {"SARIrate"},
    )
    values = normalize_units(df).set_index("countryname")["value"].to_dict()
    assert values == {"Ireland": 3500, "Luxembourg": 1300, "Malta": 8.1, "Slovakia": 0.1}


def _series(country: str, values: list[float]) -> pd.DataFrame:
    return frame(
        ili_csv(
            *[
                f"{country},2025-W{w:02d},ILIconsultationrate,total,{v}"
                for w, v in enumerate(values, 1)
            ]
        )
    )


def test_check_scale_accepts_revisions():
    check_scale(_series("Malta", [5000, 6000, 7000]), _series("Malta", [5100, 5900, 7700]), "t")


def test_check_scale_rejects_unit_change():
    local = _series("Malta", [5000, 6000, 7000])
    with pytest.raises(ValidationError, match=r"Malta ILIconsultationrate \(x0\.001\)"):
        check_scale(local, _series("Malta", [5, 6, 7]), "t")
    with pytest.raises(ValidationError, match="unit change"):
        check_scale(_series("Malta", [5, 6, 7]), local, "t")


def test_check_scale_ignores_zeros_and_small_overlaps():
    # Zeros are skipped; two overlapping weeks are too few to judge
    check_scale(_series("Malta", [0, 5, 6]), _series("Malta", [3, 5000, 6000]), "t")


def test_sync_converts_units_and_detects_upstream_unit_change(tmp_path):
    ecdc = {
        "ILIARIRates.csv": ili_csv(
            *[f"Malta,2025-W{w:02d},ILIconsultationrate,total,{w}.5" for w in range(1, 5)]
        ),
        "SARIRates.csv": ECDC_FILES["SARIRates.csv"],
    }
    sync(tmp_path, FakeSession(ecdc))
    assert (
        "Malta,2025-W01,ILIconsultationrate,total,1500\n"
        in (tmp_path / "ILIARIRates.csv").read_text()
    )

    # Re-running on the same per-100 data is a no-op
    stats = sync(tmp_path, FakeSession(ecdc))
    assert not stats["ILIARIRates.csv"].changed

    # ECDC switching Malta to per 100,000 would shift values x1000 after conversion
    switched = {
        **ecdc,
        "ILIARIRates.csv": ili_csv(
            *[f"Malta,2025-W{w:02d},ILIconsultationrate,total,{w}500" for w in range(1, 5)]
        ),
    }
    with pytest.raises(ValidationError, match="Malta"):
        sync(tmp_path, FakeSession(switched))


def test_update_metadata_keeps_extra_sources(tmp_path):
    path = tmp_path / "metadata.json"
    data = {"SARIRates.csv": frame(ECDC_FILES["SARIRates.csv"], {"SARIrate"})}
    update_metadata(path, data, "abc", extra_source="https://example.org/history.csv")
    update_metadata(path, data, "def")
    metadata = json.loads(path.read_text())
    assert metadata["data_sources"] == [ECDC_SOURCE, "https://example.org/history.csv"]
    assert metadata["ecdc_commit"] == "def"


# --- output format ----------------------------------------------------------


def test_to_csv_is_sorted_and_formats_values_exactly():
    df = frame(
        ili_csv(
            "Germany,2025-W01,ILIconsultationrate,total,0",
            "Austria,2025-W02,ILIconsultationrate,total,4345.3",
            "Austria,2025-W01,ILIconsultationrate,total,0.1",
            "Austria,2025-W01,ARIconsultationrate,total,123456.789",
        )
    )
    assert to_csv(df) == ili_csv(
        "Austria,2025-W01,ARIconsultationrate,total,123456.789",
        "Austria,2025-W01,ILIconsultationrate,total,0.1",
        "Austria,2025-W02,ILIconsultationrate,total,4345.3",
        "Germany,2025-W01,ILIconsultationrate,total,0",
    )


def test_to_csv_round_trips():
    text = ili_csv("Austria,2025-W01,ILIconsultationrate,total,857.6")
    assert to_csv(frame(text)) == text


# --- sync (end to end) ------------------------------------------------------


ECDC_FILES = {
    "ILIARIRates.csv": ili_csv("Austria,2025-W03,ILIconsultationrate,total,20"),
    "SARIRates.csv": sari_csv("Spain,2025-W03,SARIrate,65+,5.5"),
}


def test_sync_seeds_empty_data_dir(tmp_path):
    session = FakeSession(ECDC_FILES)

    stats = sync(tmp_path, session)

    assert stats["ILIARIRates.csv"].added == 1
    assert (tmp_path / "ILIARIRates.csv").read_text() == ECDC_FILES["ILIARIRates.csv"]
    assert (tmp_path / "SARIRates.csv").read_text() == ECDC_FILES["SARIRates.csv"]
    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert metadata["ecdc_commit"] == "abc123"
    assert metadata["records_count"] == {"ILIARIRates": 1, "SARIRates": 1}
    assert metadata["date_range"]["SARIRates"] == {"start": "2025-W03", "end": "2025-W03"}
    assert metadata["units"]["ILIARIRates"]["default"] == "per 100,000 population"
    assert set(metadata["units"]["ILIARIRates"]["exceptions"]) == {
        "Cyprus",
        "Finland",
        "Luxembourg",
        "Malta",
    }
    assert metadata["data_sources"] == [ECDC_SOURCE]
    # All files fetched from the resolved commit, not a moving branch
    assert all("/abc123/" in url for url in session.urls if "raw.githubusercontent" in url)


def test_sync_second_run_writes_nothing(tmp_path):
    sync(tmp_path, FakeSession(ECDC_FILES))
    before = {p.name: p.stat().st_mtime_ns for p in tmp_path.iterdir()}

    stats = sync(tmp_path, FakeSession(ECDC_FILES, commit="def456"))

    assert not any(s.changed for s in stats.values())
    assert {p.name: p.stat().st_mtime_ns for p in tmp_path.iterdir()} == before


def test_sync_preserves_local_history(tmp_path):
    (tmp_path / "ILIARIRates.csv").write_text(
        ili_csv("Austria,2015-W01,ILIconsultationrate,total,10")
    )

    stats = sync(tmp_path, FakeSession(ECDC_FILES))

    assert stats["ILIARIRates.csv"].local_only == 1
    assert (tmp_path / "ILIARIRates.csv").read_text() == ili_csv(
        "Austria,2015-W01,ILIconsultationrate,total,10",
        "Austria,2025-W03,ILIconsultationrate,total,20",
    )


def test_sync_falls_back_to_branch_when_commit_lookup_fails(tmp_path):
    session = FakeSession(ECDC_FILES, commit=None)
    sync(tmp_path, session)
    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert metadata["ecdc_commit"] is None
    assert any("/main/" in url for url in session.urls)


def test_sync_writes_nothing_if_any_file_is_invalid(tmp_path):
    files = {**ECDC_FILES, "SARIRates.csv": "garbage\n1\n"}
    with pytest.raises(ValidationError):
        sync(tmp_path, FakeSession(files))
    assert list(tmp_path.iterdir()) == []


def test_main_returns_error_on_fetch_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sync_ecdc.requests, "Session", lambda: _ContextSession({}))
    assert sync_ecdc.main(["--data-dir", str(tmp_path)]) == 1
    assert "error:" in capsys.readouterr().err


def test_main_writes_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_ecdc.requests, "Session", lambda: _ContextSession(ECDC_FILES))
    summary = tmp_path / "summary.md"
    assert (
        sync_ecdc.main(["--data-dir", str(tmp_path / "data"), "--summary-file", str(summary)]) == 0
    )
    assert "| ILIARIRates.csv | 1 | 0 | 0 | 0 |" in summary.read_text()


class _ContextSession(FakeSession):
    def __enter__(self) -> "_ContextSession":
        return self

    def __exit__(self, *args: object) -> None:
        pass
