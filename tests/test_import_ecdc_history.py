"""Tests for scripts/import_ecdc_history.py."""

import json

import pytest
import requests
from import_ecdc_history import (
    HISTORY_SOURCE,
    UNIT_SWITCH_COMMIT,
    import_history,
    list_commits,
)
from sync_ecdc import ECDC_SOURCE, ValidationError

from tests.test_sync_ecdc import FakeResponse, ili_csv, sari_csv

SARI_FILE = "SARIRates.csv"


class JsonResponse(FakeResponse):
    def __init__(self, data: object):
        super().__init__(json.dumps(data))
        self.content = self.text.encode()

    def json(self) -> object:
        return json.loads(self.text)


class HistorySession:
    """Serves ECDC file versions by commit; versions maps file -> [(sha, csv)], newest first."""

    def __init__(self, versions: dict[str, list[tuple[str, str | None]]], page_size: int = 100):
        self.versions = versions
        self.page_size = page_size
        self.urls: list[str] = []

    def get(self, url: str, params: dict | None = None, **kwargs: object) -> FakeResponse:
        self.urls.append(url)
        if "api.github.com" in url:
            assert params is not None
            name = params["path"].removeprefix("data/")
            shas = [sha for sha, _ in self.versions.get(name, [])]
            start = (params["page"] - 1) * self.page_size
            return JsonResponse([{"sha": sha} for sha in shas[start : start + self.page_size]])
        *_, sha, _, name = url.rsplit("/", 3)
        for version_sha, text in self.versions.get(name, []):
            if version_sha == sha and text is not None:
                response = FakeResponse(text)
                response.content = text.encode()  # type: ignore[attr-defined]
                return response
        return FakeResponse("not found", 404)


MASTER = sari_csv(
    "Spain,2022-W25,SARIrate,total,5",
    "Spain,2022-W26,SARIrate,total,6",
    "Spain,2022-W27,SARIrate,total,7",
)
VERSIONS = [
    # Newest first, as the commits API lists them
    (
        "c3",
        sari_csv(
            "Spain,2022-W25,SARIrate,total,5",
            "Spain,2022-W26,SARIrate,total,6",
            "Spain,2022-W27,SARIrate,total,7",
        ),
    ),
    (
        "c2",
        sari_csv(
            "Spain,2021-W25,SARIrate,total,3.5",  # newest version with this week: kept
            "Spain,2022-W25,SARIrate,total,4.9",  # in master: master wins
            "Spain,2022-W26,SARIrate,total,6",
            "Spain,2022-W27,SARIrate,total,7",
            "Spain,2022-W28,SARIrate,total,8",  # removed within ECDC's window: left out
            "Ireland,2021-W25,SARIrate,total,0.2",  # per 100 admissions: x1000
        ),
    ),
    (
        "c1",
        sari_csv(
            "Spain,2020-W40,SARIrate,total,1",  # only in the oldest version: kept
            "Spain,2021-W25,SARIrate,total,3",  # revised later: c2 wins
            "Malta,2020-W41,SARIrate,total,0",  # all-zero series: dropped as missing
            "Malta,2020-W42,SARIrate,total,0",
        ),
    ),
]


@pytest.fixture
def data_dir(tmp_path):
    (tmp_path / "ILIARIRates.csv").write_text(
        ili_csv("Austria,2024-W01,ILIconsultationrate,total,1")
    )
    (tmp_path / SARI_FILE).write_text(MASTER)
    (tmp_path / "metadata.json").write_text(
        json.dumps({"ecdc_commit": "abc123", "data_sources": [ECDC_SOURCE]})
    )
    return tmp_path


def run(data_dir, versions=VERSIONS, cache_dir=None):
    session = HistorySession({SARI_FILE: versions})
    cache = cache_dir or data_dir / "cache"
    return import_history(data_dir, session, cache, [SARI_FILE]), session


def test_list_commits_follows_pages():
    session = HistorySession({SARI_FILE: [(f"c{i}", "") for i in range(5)]}, page_size=2)
    shas = list_commits(session, SARI_FILE)  # type: ignore[arg-type]
    assert shas == ["c0", "c1", "c2", "c3", "c4"]


def test_import_takes_newest_version_of_missing_rows(data_dir):
    added, _ = run(data_dir)

    assert added == {SARI_FILE: 3}
    assert (data_dir / SARI_FILE).read_text() == sari_csv(
        "Ireland,2021-W25,SARIrate,total,200",
        "Spain,2020-W40,SARIrate,total,1",
        "Spain,2021-W25,SARIrate,total,3.5",
        "Spain,2022-W25,SARIrate,total,5",
        "Spain,2022-W26,SARIrate,total,6",
        "Spain,2022-W27,SARIrate,total,7",
    )
    metadata = json.loads((data_dir / "metadata.json").read_text())
    assert metadata["ecdc_commit"] == "abc123"
    assert metadata["data_sources"] == [ECDC_SOURCE, HISTORY_SOURCE]
    assert metadata["date_range"]["SARIRates"] == {"start": "2020-W40", "end": "2022-W27"}


def test_import_is_idempotent_and_uses_cache(data_dir):
    run(data_dir)
    before = (data_dir / SARI_FILE).read_text()

    added, session = run(data_dir)
    assert added == {SARI_FILE: 0}
    assert (data_dir / SARI_FILE).read_text() == before
    assert all("api.github.com" in url for url in session.urls)


def test_import_keeps_greece_latvia_sari_unscaled_before_unit_switch(data_dir):
    # Master, synced since the switch, has Greece per 100 admissions x1000
    master = sari_csv(
        "Greece,2022-W30,SARIrate,total,4000",
        "Greece,2022-W31,SARIrate,total,5000",
        "Greece,2022-W32,SARIrate,total,6000",
    )
    (data_dir / SARI_FILE).write_text(master)
    versions = [
        # From the switch on, ECDC publishes per 100 admissions
        (
            UNIT_SWITCH_COMMIT,
            sari_csv(
                "Greece,2022-W30,SARIrate,total,4",
                "Greece,2022-W31,SARIrate,total,5",
                "Greece,2022-W32,SARIrate,total,6",
            ),
        ),
        # Older versions already have per 100,000: kept as published, so they match the
        # master on the overlapping weeks instead of failing the scale check
        (
            "older",
            sari_csv(
                "Greece,2021-W01,SARIrate,total,3000",
                "Greece,2022-W30,SARIrate,total,4000",
                "Greece,2022-W31,SARIrate,total,5000",
                "Greece,2022-W32,SARIrate,total,6000",
                "Latvia,2021-W01,SARIrate,total,2500",
                "Ireland,2021-W01,SARIrate,total,0.2",  # not affected: still x1000
            ),
        ),
    ]
    added, _ = run(data_dir, versions)

    assert added == {SARI_FILE: 3}
    assert (data_dir / SARI_FILE).read_text() == sari_csv(
        "Greece,2021-W01,SARIrate,total,3000",
        "Greece,2022-W30,SARIrate,total,4000",
        "Greece,2022-W31,SARIrate,total,5000",
        "Greece,2022-W32,SARIrate,total,6000",
        "Ireland,2021-W01,SARIrate,total,200",
        "Latvia,2021-W01,SARIrate,total,2500",
    )


def test_import_without_trimmed_history_changes_nothing(data_dir):
    metadata = (data_dir / "metadata.json").read_text()
    added, _ = run(data_dir, VERSIONS[:1])
    assert added == {SARI_FILE: 0}
    assert (data_dir / SARI_FILE).read_text() == MASTER
    assert (data_dir / "metadata.json").read_text() == metadata


def test_import_rejects_scale_change_between_versions(data_dir):
    versions = [
        VERSIONS[0],
        (
            "c2",
            sari_csv(
                "Spain,2021-W01,SARIrate,total,3",
                "Spain,2021-W02,SARIrate,total,3",
                "Spain,2021-W03,SARIrate,total,3",
            ),
        ),
        (
            "c1",
            sari_csv(
                "Spain,2021-W01,SARIrate,total,3000",
                "Spain,2021-W02,SARIrate,total,3000",
                "Spain,2021-W03,SARIrate,total,3000",
            ),
        ),
    ]
    with pytest.raises(ValidationError, match="c1"):
        run(data_dir, versions)
    assert (data_dir / SARI_FILE).read_text() == MASTER


def test_import_writes_nothing_if_a_download_fails(data_dir):
    versions = [*VERSIONS[:2], ("c1", None)]  # listed but not downloadable
    with pytest.raises(requests.HTTPError):
        run(data_dir, versions)
    assert (data_dir / SARI_FILE).read_text() == MASTER
