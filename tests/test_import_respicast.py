"""Tests for scripts/import_respicast.py."""

import io
import json

import pandas as pd
import pytest
from import_respicast import (
    RESPICAST_SOURCE,
    drop_all_zero_series,
    import_respicast,
    to_master_format,
)
from sync_ecdc import ECDC_SOURCE, ValidationError, read_csv

from tests.test_sync_ecdc import FakeSession, ili_csv, sari_csv

RC_HEADER = "target,location,truth_date,year_week,value\n"


def rc_csv(target: str, *rows: str) -> str:
    return RC_HEADER + "".join(f"{target},{row}\n" for row in rows)


def raw(text: str) -> pd.DataFrame:
    return read_csv(io.StringIO(text))


def test_to_master_format_maps_columns_and_countries():
    df = to_master_format(
        raw(rc_csv("ILI incidence", "GR,2015-01-04,2015-W01,290", "MT,2015-01-04,2015-W01,4200")),
        "ILIconsultationrate",
    )
    assert df.to_dict("records") == [
        {
            "survtype": "primary care syndromic",
            "countryname": "Greece",
            "yearweek": "2015-W01",
            "indicator": "ILIconsultationrate",
            "age": "total",
            "value": "290",
        },
        {
            "survtype": "primary care syndromic",
            "countryname": "Malta",
            "yearweek": "2015-W01",
            "indicator": "ILIconsultationrate",
            "age": "total",
            "value": "4200",
        },
    ]


@pytest.mark.parametrize(
    "text, message",
    [
        (rc_csv("ILI incidence", "XX,2015-01-04,2015-W01,1"), "unknown location"),
        (rc_csv("ARI incidence", "AT,2015-01-04,2015-W01,1"), "unexpected targets"),
        ("a,b\n1,2\n", "expected columns"),
    ],
)
def test_to_master_format_rejects_bad_input(text, message):
    with pytest.raises(ValidationError, match=message):
        to_master_format(raw(text), "ILIconsultationrate")


def test_drop_all_zero_series():
    df = pd.DataFrame(
        {
            "countryname": ["Malta", "Malta", "Slovenia", "Slovenia"],
            "indicator": ["ARIconsultationrate"] * 4,
            "value": [0.0, 0.0, 0.0, 5.0],
        }
    )
    kept, dropped = drop_all_zero_series(df)
    assert kept["countryname"].tolist() == ["Slovenia", "Slovenia"]
    assert dropped == ["Malta ARIconsultationrate (2 rows)"]


MASTER = ili_csv(
    "Austria,2024-W01,ILIconsultationrate,total,1500",
    "Austria,2024-W02,ILIconsultationrate,total,1600",
    "Austria,2024-W03,ILIconsultationrate,total,1700",
    "Austria,2024-W01,ILIconsultationrate,0-4,900",
)
RESPICAST = {
    "2024-10-11-ILI_incidence.csv": rc_csv(
        "ILI incidence",
        "AT,2015-01-04,2015-W01,800",  # history: added
        "AT,2024-01-07,2024-W01,1490",  # overlap: master wins
        "AT,2024-01-14,2024-W02,1600",
        "AT,2024-01-21,2024-W03,1700",
        "AT,2024-01-28,2024-W04,1750",  # gap in master: added
    ),
    "2024-10-11-ARI_incidence.csv": rc_csv(
        "ARI incidence",
        "MT,2015-01-04,2015-W01,0",  # all-zero series: dropped
        "MT,2015-01-11,2015-W02,0",
        "SI,2015-01-04,2015-W01,0",  # zero in a non-zero series: kept
        "SI,2015-01-11,2015-W02,950",
    ),
}


@pytest.fixture
def data_dir(tmp_path):
    (tmp_path / "ILIARIRates.csv").write_text(MASTER)
    (tmp_path / "SARIRates.csv").write_text(sari_csv("Spain,2025-W03,SARIrate,65+,5.5"))
    (tmp_path / "metadata.json").write_text(
        json.dumps({"ecdc_commit": "abc123", "data_sources": [ECDC_SOURCE]})
    )
    return tmp_path


def test_import_fills_gaps_and_keeps_master_values(data_dir, capsys):
    added = import_respicast(data_dir, FakeSession(RESPICAST))

    assert added == 4
    assert "dropped all-zero series: Malta ARIconsultationrate (2 rows)" in capsys.readouterr().out
    assert (data_dir / "ILIARIRates.csv").read_text() == ili_csv(
        "Slovenia,2015-W01,ARIconsultationrate,total,0",
        "Slovenia,2015-W02,ARIconsultationrate,total,950",
        "Austria,2015-W01,ILIconsultationrate,total,800",
        "Austria,2024-W01,ILIconsultationrate,0-4,900",
        "Austria,2024-W01,ILIconsultationrate,total,1500",
        "Austria,2024-W02,ILIconsultationrate,total,1600",
        "Austria,2024-W03,ILIconsultationrate,total,1700",
        "Austria,2024-W04,ILIconsultationrate,total,1750",
    )
    metadata = json.loads((data_dir / "metadata.json").read_text())
    assert metadata["ecdc_commit"] == "abc123"
    assert metadata["data_sources"] == [ECDC_SOURCE, RESPICAST_SOURCE]
    assert metadata["records_count"] == {"ILIARIRates": 8, "SARIRates": 1}
    assert metadata["date_range"]["ILIARIRates"] == {"start": "2015-W01", "end": "2024-W04"}


def test_import_is_idempotent(data_dir):
    import_respicast(data_dir, FakeSession(RESPICAST))
    before = (data_dir / "ILIARIRates.csv").read_text()
    assert import_respicast(data_dir, FakeSession(RESPICAST)) == 0
    assert (data_dir / "ILIARIRates.csv").read_text() == before


def test_import_rejects_scale_mismatch(data_dir):
    files = {
        **RESPICAST,
        "2024-10-11-ILI_incidence.csv": rc_csv(
            "ILI incidence",
            "AT,2024-01-07,2024-W01,1.5",
            "AT,2024-01-14,2024-W02,1.6",
            "AT,2024-01-21,2024-W03,1.7",
        ),
    }
    with pytest.raises(ValidationError, match="Austria"):
        import_respicast(data_dir, FakeSession(files))
    assert (data_dir / "ILIARIRates.csv").read_text() == MASTER
