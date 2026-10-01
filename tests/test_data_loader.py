"""Tests for pyerviss.data_loader and pyerviss.cache."""

import json

import pytest
import requests
import responses

from pyerviss import data_loader
from pyerviss.cache import clear_cache, get_cache_dir
from pyerviss.data_loader import (
    DEFAULT_DATA_URL,
    fetch_file,
    get_metadata,
    load_csv,
    update_data,
)
from pyerviss.exceptions import DataFetchError

URL = DEFAULT_DATA_URL + "SARIRates.csv"
CSV = (
    "survtype,countryname,yearweek,indicator,age,value\n"
    "SARI syndromic,Spain,2025-W03,SARIrate,65+,5.5\n"
    "SARI syndromic,Spain,2025-W03,SARIrate,total,0\n"
)
CSV_V2 = CSV.replace("5.5", "6.5")


def serve(body: str = CSV, etag: str = '"v1"', url: str = URL) -> None:
    responses.add(responses.GET, url, body=body, headers={"ETag": etag})


def not_modified(url: str = URL) -> None:
    responses.add(responses.GET, url, status=304)


def advance_clock(monkeypatch, seconds: float) -> None:
    now = data_loader.time.time()
    monkeypatch.setattr(data_loader.time, "time", lambda: now + seconds)


# --- cache directory --------------------------------------------------------


def test_cache_dir_uses_env_override(isolated_cache):
    assert get_cache_dir() == isolated_cache
    assert isolated_cache.is_dir()


def test_clear_cache_removes_files(isolated_cache):
    (get_cache_dir() / "SARIRates.csv").write_text(CSV)
    clear_cache()
    assert not isolated_cache.exists()
    clear_cache()  # clearing an absent cache is fine


# --- fetch_file -------------------------------------------------------------


@responses.activate
def test_first_fetch_downloads(isolated_cache):
    serve()
    path = fetch_file("SARIRates.csv")
    assert path == isolated_cache / "SARIRates.csv"
    assert path.read_text() == CSV
    assert len(responses.calls) == 1


@responses.activate
def test_fetch_within_interval_makes_no_request():
    serve()
    fetch_file("SARIRates.csv")
    fetch_file("SARIRates.csv")
    assert len(responses.calls) == 1


@responses.activate
def test_fetch_after_interval_sends_etag_and_keeps_file_on_304(monkeypatch):
    serve()
    path = fetch_file("SARIRates.csv")
    advance_clock(monkeypatch, data_loader.CHECK_INTERVAL_SECONDS + 1)
    not_modified()

    assert fetch_file("SARIRates.csv").read_text() == CSV
    assert responses.calls[1].request.headers["If-None-Match"] == '"v1"'

    # The 304 counts as a check: no new request until the interval passes again
    fetch_file("SARIRates.csv")
    assert len(responses.calls) == 2
    assert path.read_text() == CSV


@responses.activate
def test_fetch_after_interval_downloads_changed_file(monkeypatch):
    serve()
    fetch_file("SARIRates.csv")
    advance_clock(monkeypatch, data_loader.CHECK_INTERVAL_SECONDS + 1)
    responses.replace(responses.GET, URL, body=CSV_V2, headers={"ETag": '"v2"'})

    assert fetch_file("SARIRates.csv").read_text() == CSV_V2


@responses.activate
def test_force_refresh_checks_immediately():
    serve()
    fetch_file("SARIRates.csv")
    not_modified()
    fetch_file("SARIRates.csv", force_refresh=True)
    assert len(responses.calls) == 2


@responses.activate
def test_fetch_failure_without_cache_raises():
    responses.add(responses.GET, URL, status=404)
    with pytest.raises(DataFetchError, match="Could not download"):
        fetch_file("SARIRates.csv")


@responses.activate
def test_fetch_failure_with_cache_warns_and_uses_cache():
    serve()
    fetch_file("SARIRates.csv")
    responses.replace(responses.GET, URL, body=requests.ConnectionError("offline"))

    with pytest.warns(UserWarning, match="using cached copy"):
        path = fetch_file("SARIRates.csv", force_refresh=True)
    assert path.read_text() == CSV


@responses.activate
def test_failed_download_leaves_cached_file_intact():
    serve()
    fetch_file("SARIRates.csv")
    responses.replace(responses.GET, URL, status=500)
    with pytest.warns(UserWarning):
        fetch_file("SARIRates.csv", force_refresh=True)
    assert (get_cache_dir() / "SARIRates.csv").read_text() == CSV
    assert not (get_cache_dir() / "SARIRates.csv.partial").exists()


@responses.activate
def test_corrupt_state_file_triggers_fresh_check():
    serve()
    path = fetch_file("SARIRates.csv")
    path.with_name("SARIRates.csv.state.json").write_text("{not json")
    not_modified()
    fetch_file("SARIRates.csv")
    assert len(responses.calls) == 2
    assert "If-None-Match" not in responses.calls[1].request.headers


@responses.activate
def test_data_url_env_override(monkeypatch):
    monkeypatch.setenv(data_loader.DATA_URL_ENV, "https://example.org/mirror")
    serve(url="https://example.org/mirror/SARIRates.csv")
    assert fetch_file("SARIRates.csv").read_text() == CSV


# --- load_csv / metadata ----------------------------------------------------


@responses.activate
def test_load_csv_types():
    serve()
    df = load_csv("SARIRates.csv")
    assert list(df.columns) == ["survtype", "countryname", "yearweek", "indicator", "age", "value"]
    assert df["value"].tolist() == [5.5, 0.0]
    assert str(df["value"].dtype) == "float64"
    assert df["age"].tolist() == ["65+", "total"]


@responses.activate
def test_load_csv_returns_independent_copies():
    serve()
    first = load_csv("SARIRates.csv")
    first.loc[0, "value"] = -1
    assert load_csv("SARIRates.csv")["value"].tolist() == [5.5, 0.0]


@responses.activate
def test_load_csv_reparses_when_file_changes(monkeypatch):
    serve()
    assert load_csv("SARIRates.csv")["value"].iloc[0] == 5.5
    advance_clock(monkeypatch, data_loader.CHECK_INTERVAL_SECONDS + 1)
    responses.replace(responses.GET, URL, body=CSV_V2, headers={"ETag": '"v2"'})
    assert load_csv("SARIRates.csv")["value"].iloc[0] == 6.5


@responses.activate
def test_load_csv_unreadable_file_suggests_clear_cache():
    serve(body="survtype,countryname,yearweek,indicator,age,value\nx,y,z,w,v,not-a-number\n")
    with pytest.raises(DataFetchError, match="clear_cache"):
        load_csv("SARIRates.csv")


@responses.activate
def test_get_metadata():
    metadata = {"last_update": "2026-10-01", "records_count": {"SARIRates": 2}}
    serve(body=json.dumps(metadata), url=DEFAULT_DATA_URL + "metadata.json")
    assert get_metadata() == metadata


@responses.activate
def test_update_data_checks_every_file():
    for name in ["ILIARIRates.csv", "SARIRates.csv", "metadata.json"]:
        serve(body="{}" if name.endswith("json") else CSV, url=DEFAULT_DATA_URL + name)
    update_data()
    update_data()  # forced: checks again despite the interval
    assert len(responses.calls) == 6
    assert sorted(p.name for p in get_cache_dir().glob("*") if "state" not in p.name) == [
        "ILIARIRates.csv",
        "SARIRates.csv",
        "metadata.json",
    ]
