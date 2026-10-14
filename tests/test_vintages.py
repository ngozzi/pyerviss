"""Tests for as_of queries, on a fake ECDC snapshot folder and a small mirror."""

import json
import time
from datetime import date, datetime

import pandas as pd
import pytest
import responses

import pyerviss as pv
from pyerviss import api, vintages
from pyerviss.exceptions import DataFetchError, InvalidParameterError

RATE_HEADER = "survtype,countryname,yearweek,indicator,age,value\n"
VIROLOGY_HEADER = (
    "survtype,countryname,yearweek,pathogen,pathogentype,pathogensubtype,indicator,age,value\n"
)
WEEKS = ["2024-W40", "2024-W41", "2024-W42", "2024-W43", "2024-W44", "2024-W45"]


def rates(*rows: tuple[str, str, str, str, float]) -> str:
    """CSV text from (country, week, indicator, age, value) rows."""
    return RATE_HEADER + "".join(f"s,{c},{w},{i},{a},{v}\n" for c, w, i, a, v in rows)


def virology(*rows: tuple[str, str, str, float]) -> str:
    """Influenza rows from (country, week, indicator, value)."""
    return VIROLOGY_HEADER + "".join(
        f"s,{c},{w},Influenza,Influenza,total,{i},total,{v}\n" for c, w, i, v in rows
    )


def frame(text: str) -> pd.DataFrame:
    from io import StringIO

    df = pd.read_csv(StringIO(text), dtype=str, keep_default_na=False, na_values=[""])
    df["value"] = df["value"].astype("float64")
    return df


# Current (revised) data: 100 + week index, so mirror values are easy to tell apart
MIRROR = {
    "ILIARIRates.csv": rates(
        *[("Italy", w, "ILIconsultationrate", "total", 100 + i) for i, w in enumerate(WEEKS)],
        *[("Italy", w, "ARIconsultationrate", "total", 200 + i) for i, w in enumerate(WEEKS)],
        *[("Malta", w, "ILIconsultationrate", "total", 3000 + i) for i, w in enumerate(WEEKS)],
        *[("Spain", w, "ILIconsultationrate", "total", 300 + i) for i, w in enumerate(WEEKS)],
    ),
    "SARIRates.csv": rates(
        *[("Greece", w, "SARIrate", "total", 4000 + i) for i, w in enumerate(WEEKS)],
        *[("Ireland", w, "SARIrate", "total", 5000 + i) for i, w in enumerate(WEEKS)],
    ),
    "sentinelTestsDetectionsPositivity.csv": virology(
        *[
            row
            for i, w in enumerate(WEEKS)
            for row in [
                ("Italy", w, "tests", 100),
                ("Italy", w, "detections", 10 + i),
                ("Italy", w, "positivity", 10 + i),
            ]
        ]
    ),
    "SARITestsDetectionsPositivity.csv": VIROLOGY_HEADER,
}

# Snapshots as ECDC published them: per-100 rates, mixed-case names, one empty file
SNAPSHOTS = {
    "2024-11-01_iliarirates.csv": rates(
        ("Italy", "2024-W42", "ILIconsultationrate", "total", 10),
        ("Italy", "2024-W43", "ILIconsultationrate", "total", 11),
        ("Malta", "2024-W43", "ILIconsultationrate", "total", 2.9),
    ),
    "2024-11-08_ILIARIRates.csv": rates(
        ("Italy", "2024-W42", "ILIconsultationrate", "total", 20),
        ("Italy", "2024-W43", "ILIconsultationrate", "total", 21),
        ("Italy", "2024-W44", "ILIconsultationrate", "total", 22),
    ),
    "2025-10-17_SARIRates.csv": rates(
        ("Greece", "2024-W44", "SARIrate", "total", 3.8),
        ("Ireland", "2024-W44", "SARIrate", "total", 4.4),
    ),
    "2025-10-24_SARIRates.csv": rates(
        ("Greece", "2024-W44", "SARIrate", "total", 3.8),
        ("Ireland", "2024-W44", "SARIrate", "total", 4.4),
    ),
    "2024-10-25_sentineltestsDetectionsPositivity.csv": "",
    "2024-11-01_sentinelTestsDetectionsPositivity.csv": virology(
        ("Italy", "2024-W43", "tests", 50),
        ("Italy", "2024-W43", "detections", 5),
        ("Italy", "2024-W43", "positivity", 10),
    ),
    "2024-11-01_variants.csv": "unrelated\n",
}


@pytest.fixture(autouse=True)
def fake_ecdc(tmp_path, monkeypatch):
    folder = tmp_path / "snapshots"
    folder.mkdir()
    for name, text in SNAPSHOTS.items():
        (folder / name).write_text(text)

    def tree_entries():
        return [{"path": p.name, "size": p.stat().st_size} for p in folder.iterdir()]

    def load_csv(file_name: str) -> pd.DataFrame:
        return frame(MIRROR[file_name])

    monkeypatch.setattr(vintages, "_tree_entries", tree_entries)
    monkeypatch.setattr(vintages, "fetch_snapshot", lambda name: folder / name)
    monkeypatch.setattr(vintages, "load_csv", load_csv)
    monkeypatch.setattr(api, "load_csv", load_csv)


def values(df: pd.DataFrame, country: str) -> list[tuple]:
    rows = df[df["country"] == country]
    return [
        (w, v, None if pd.isna(t) else t.date())
        for w, v, t in rows[["year_week", "value", "vintage"]].itertuples(index=False)
    ]


# --- choosing a vintage -----------------------------------------------------


def test_uses_latest_snapshot_on_or_before_as_of():
    assert values(pv.get_ili(countries="Italy", as_of="2024-11-07"), "Italy") == [
        ("2024-W40", 100, None),
        ("2024-W41", 101, None),
        ("2024-W42", 10, date(2024, 11, 1)),
        ("2024-W43", 11, date(2024, 11, 1)),
    ]
    # A snapshot dated exactly as_of is used
    later = pv.get_ili(countries="Italy", as_of=date(2024, 11, 8))
    assert later["value"].tolist() == [100, 101, 20, 21, 22]


@pytest.mark.parametrize("as_of", ["2024-11-07", date(2024, 11, 7), datetime(2024, 11, 7, 9)])
def test_as_of_formats(as_of):
    assert pv.get_ili(countries="Italy", as_of=as_of)["vintage"].max() == pd.Timestamp("2024-11-01")


@pytest.mark.parametrize("as_of", ["yesterday", "2024-13-01", 20241107])
def test_invalid_as_of(as_of):
    with pytest.raises(InvalidParameterError, match="as_of"):
        pv.get_ili(as_of=as_of)


def test_no_revised_values_or_later_weeks_leak():
    df = pv.get_ili(as_of="2024-11-07")
    assert df["year_week"].max() == "2024-W43"
    snapshot_rows = df[df["vintage"].notna()]
    assert set(snapshot_rows["value"]) == {10, 11, 2900}


def test_history_is_cut_per_series():
    df = pv.get_ili(as_of="2024-11-07")
    # Malta's series starts at W43 in the snapshot, so W40-W42 come from the mirror
    assert values(df, "Malta") == [
        ("2024-W40", 3000, None),
        ("2024-W41", 3001, None),
        ("2024-W42", 3002, None),
        ("2024-W43", 2900, date(2024, 11, 1)),
    ]
    # Spain isn't in the snapshot: cut at the snapshot's first week overall (W42)
    assert values(df, "Spain") == [("2024-W40", 300, None), ("2024-W41", 301, None)]
    # Same for a series of another indicator in the same file
    assert pv.get_ari(as_of="2024-11-07")["year_week"].tolist() == ["2024-W40", "2024-W41"]


def test_case_insensitive_names_and_empty_files():
    assert pv.list_vintages("ili") == [date(2024, 11, 1), date(2024, 11, 8)]
    # The 0-byte 2024-10-25 file is skipped
    assert pv.list_vintages("positivity", "primary care") == [date(2024, 11, 1)]
    assert pv.list_vintages("positivity") == [date(2024, 11, 1)]
    assert pv.list_vintages("sari") == [date(2025, 10, 17), date(2025, 10, 24)]
    with pytest.raises(InvalidParameterError):
        pv.list_vintages("ili", setting="hospital")


# --- units ------------------------------------------------------------------


def test_per_100_rates_are_rescaled():
    df = pv.get_ili(countries="Malta", as_of="2024-11-07")
    assert df["value"].iloc[-1] == 2900


def test_greece_sari_rescaled_only_after_ecdc_switched_units():
    before = pv.get_sari(as_of="2025-10-17", start="2024-W44")
    after = pv.get_sari(as_of="2025-10-24", start="2024-W44")
    assert dict(zip(before["country"], before["value"], strict=True)) == {
        "Greece": 3.8,
        "Ireland": 4400,
    }
    assert dict(zip(after["country"], after["value"], strict=True)) == {
        "Greece": 3800,
        "Ireland": 4400,
    }


# --- warnings and reconstruction --------------------------------------------


def test_warns_when_snapshot_is_old():
    with pytest.warns(UserWarning, match="from 2024-11-08"):
        pv.get_ili(as_of="2024-11-30")


def test_reconstructs_before_first_snapshot():
    # W41 ends Sunday 2024-10-13 and counts as published five days later
    with pytest.warns(UserWarning, match="later revisions"):
        df = pv.get_ili(countries="Italy", as_of="2024-10-17")
    assert values(df, "Italy") == [("2024-W40", 100, None)]
    with pytest.warns(UserWarning):
        df = pv.get_ili(countries="Italy", as_of="2024-10-18")
    assert df["year_week"].tolist() == ["2024-W40", "2024-W41"]


# --- other functions --------------------------------------------------------


def test_positivity_as_of():
    df = pv.get_positivity(setting="primary care", as_of="2024-11-07")
    assert list(df.columns) == [*api.POSITIVITY_COLUMNS, "vintage"]
    assert df[["year_week", "value", "tests"]].values.tolist() == [
        ["2024-W40", 10, 100],
        ["2024-W41", 11, 100],
        ["2024-W42", 12, 100],
        ["2024-W43", 10, 50],
    ]
    assert df["vintage"].notna().tolist() == [False, False, False, True]


def test_latest_week_and_coverage_as_of():
    assert pv.latest_week("ili", as_of="2024-11-07") == "2024-W43"
    assert pv.latest_week("ili", as_of="2024-11-08") == "2024-W44"
    cov = pv.coverage("ili", as_of="2024-11-07").set_index("country")
    assert cov.loc["Malta", "last_week"] == "2024-W43"


def test_without_as_of_output_is_unchanged():
    df = pv.get_ili()
    assert list(df.columns) == api.COLUMNS
    assert df["year_week"].max() == "2024-W45"


def test_with_as_of_vintage_is_last_column():
    df = pv.get_ili(as_of="2024-11-07")
    assert list(df.columns) == [*api.COLUMNS, "vintage"]
    assert str(df["vintage"].dtype) == "datetime64[ns]"


# --- snapshot listing and download ------------------------------------------


REAL_TREE_ENTRIES = vintages._tree_entries
REAL_FETCH_SNAPSHOT = vintages.fetch_snapshot


@pytest.fixture
def github(monkeypatch):
    monkeypatch.setattr(vintages, "_tree_entries", REAL_TREE_ENTRIES)
    monkeypatch.setattr(vintages, "fetch_snapshot", REAL_FETCH_SNAPSHOT)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with responses.RequestsMock() as mock:
        yield mock


TREE = {
    "tree": [
        {"path": "2023-11-24_ILIARIRates.csv", "size": 100},
        {"path": "2023-11-24_sentineltestsDetectionsPositivity.csv", "size": 0},
        {"path": "2023-12-01_sentineltestsDetectionsPositivity.csv", "size": 100},
        {"path": "2023-11-24_variants.csv", "size": 100},
        {"path": "README.md", "size": 10},
    ],
    "truncated": False,
}


def test_snapshot_index_from_github(github, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    github.get(vintages.SNAPSHOTS_TREE_URL, json=TREE)
    index = vintages.snapshot_index()
    assert index["ILIARIRates.csv"] == [(date(2023, 11, 24), "2023-11-24_ILIARIRates.csv")]
    assert index["sentinelTestsDetectionsPositivity.csv"] == [
        (date(2023, 12, 1), "2023-12-01_sentineltestsDetectionsPositivity.csv")
    ]
    assert index["SARIRates.csv"] == []
    assert github.calls[0].request.headers["Authorization"] == "Bearer secret"
    # Cached: no second request within the hour
    vintages.snapshot_index()
    assert len(github.calls) == 1


def test_snapshot_index_falls_back_to_stale_copy(github, isolated_cache):
    index = isolated_cache / "snapshots" / vintages.INDEX_FILE
    index.parent.mkdir(parents=True)
    stale = {"checked_at": time.time() - 2 * vintages.INDEX_CHECK_SECONDS, "entries": TREE["tree"]}
    index.write_text(json.dumps(stale))
    github.get(vintages.SNAPSHOTS_TREE_URL, status=500)
    with pytest.warns(UserWarning, match="Could not list"):
        assert vintages.snapshot_dates("ILIARIRates.csv") == [date(2023, 11, 24)]


def test_snapshot_index_fails_without_cache(github):
    github.get(vintages.SNAPSHOTS_TREE_URL, status=500)
    with pytest.raises(DataFetchError):
        vintages.snapshot_index()


def test_snapshots_are_downloaded_once(github):
    name = "2023-11-24_ILIARIRates.csv"
    github.get(vintages.SNAPSHOT_URL.format(name=name), body="a,b\n")
    path = vintages.fetch_snapshot(name)
    assert vintages.fetch_snapshot(name) == path
    assert path.read_text() == "a,b\n"
    assert len(github.calls) == 1
