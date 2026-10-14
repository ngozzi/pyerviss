"""Tests for get_detections, on small in-memory virology files."""

from io import StringIO

import pandas as pd
import pytest

import pyerviss as pv
from pyerviss import api
from pyerviss.exceptions import DataNotFoundError, InvalidParameterError

HEADER = "survtype,countryname,yearweek,pathogen,pathogentype,pathogensubtype,indicator,age,value\n"

SENTINEL = HEADER + "".join(
    f"s,{row}\n"
    for row in [
        # Italy 2024-W50: pathogen-level rows, then the breakdown (ECDC omits zeros)
        "Italy,2024-W50,Influenza,Influenza,total,detections,total,100",
        "Italy,2024-W50,Influenza,Influenza,total,tests,total,300",
        "Italy,2024-W50,Influenza,Influenza,total,positivity,total,33.3",
        "Italy,2024-W50,Influenza,Influenza A,A(H3),detections,total,50",
        "Italy,2024-W50,Influenza,Influenza A,A(H1)pdm09,detections,total,20",
        "Italy,2024-W50,Influenza,Influenza A,A (unknown),detections,total,10",
        "Italy,2024-W50,Influenza,Influenza B,B/Vic,detections,total,8",
        "Italy,2024-W50,Influenza,Influenza B,B (unknown),detections,total,2",
        "Italy,2024-W50,Influenza,Influenza untyped,Influenza untyped,detections,total,6",
        "Italy,2024-W50,Influenza,Influenza unknown,unk,detections,total,4",
        "Italy,2024-W50,RSV,RSV,RSV,detections,total,12",
        "Italy,2024-W50,RSV,RSV-A,NA,detections,total,3",
        "Italy,2024-W50,RSV,RSV-B,NA,detections,total,6",
        "Italy,2024-W50,RSV,RSV untyped,NA,detections,total,3",
        "Italy,2024-W50,SARS-CoV-2,SARS-CoV-2,SARS-CoV-2,detections,total,7",
        # Italy 2024-W51: only H3
        "Italy,2024-W51,Influenza,Influenza,total,detections,total,40",
        "Italy,2024-W51,Influenza,Influenza A,A(H3),detections,total,40",
        # Malta 2025-W02: B/Yamagata only
        "Malta,2025-W02,Influenza,Influenza,total,detections,total,5",
        "Malta,2025-W02,Influenza,Influenza B,B/Yam,detections,total,5",
        # Sweden: SARS-CoV-2 only
        "Sweden,2024-W50,SARS-CoV-2,SARS-CoV-2,SARS-CoV-2,detections,total,3",
    ]
)
SARI = HEADER + "".join(
    f"s,{row}\n"
    for row in [
        "Spain,2025-W02,Influenza,Influenza,total,detections,total,90",
        "Spain,2025-W02,Influenza,Influenza A,A(H1)pdm09,detections,total,30",
        "Spain,2025-W02,Influenza,Influenza B,B/Vic,detections,total,60",
    ]
)
FILES = {
    "sentinelTestsDetectionsPositivity.csv": SENTINEL,
    "SARITestsDetectionsPositivity.csv": SARI,
}


def frame(text: str) -> pd.DataFrame:
    df = pd.read_csv(StringIO(text), dtype=str, keep_default_na=False, na_values=[""])
    df["value"] = df["value"].astype("float64")
    return df


@pytest.fixture(autouse=True)
def sample_data(monkeypatch):
    monkeypatch.setattr(api, "load_csv", lambda file_name: frame(FILES[file_name]))


def categories(df: pd.DataFrame, column: str = "type") -> list[tuple]:
    return list(df[[column, "value", "share", "total"]].itertuples(index=False, name=None))


# --- levels -----------------------------------------------------------------


def test_type_level_sums_subtypes():
    df = pv.get_detections("flu", "primary care", "Italy", end="2024-W50")
    assert list(df.columns) == [c for c in api.DETECTION_COLUMNS if c != "subtype"]
    # A = 50 + 20 + 10; untyped merges "Influenza untyped" and "Influenza unknown"
    assert categories(df) == [
        ("A", 80, 0.8, 100),
        ("B", 10, 0.1, 100),
        ("untyped", 10, 0.1, 100),
    ]


def test_subtype_level_labels_and_order():
    df = pv.get_detections("flu", "primary care", "Italy", end="2024-W50", level="subtype")
    assert list(df.columns) == api.DETECTION_COLUMNS
    assert list(zip(df["type"], df["subtype"], df["value"], strict=True)) == [
        ("A", "A(H1)pdm09", 20),
        ("A", "A(H3)", 50),
        ("A", "A (unknown)", 10),
        ("B", "B/Victoria", 8),
        ("B", "B (unknown)", 2),
        ("untyped", "untyped", 10),
    ]


def test_b_yamagata_label():
    df = pv.get_detections("flu", countries="Malta", level="subtype")
    assert categories(df, "subtype") == [("B/Yamagata", 5, 1.0, 5)]


def test_rsv_subtype_is_its_type():
    for level in ["type", "subtype"]:
        df = pv.get_detections("rsv", countries="IT", level=level)
        assert categories(df, level) == [
            ("RSV-A", 3, 0.25, 12),
            ("RSV-B", 6, 0.5, 12),
            ("untyped", 3, 0.25, 12),
        ]


def test_shares_add_up_to_one_per_week():
    df = pv.get_detections(level="subtype")
    sums = df.groupby(["setting", "pathogen", "country", "year_week"])["share"].sum()
    assert sums.round(9).eq(1).all()
    totals = df.groupby(["setting", "pathogen", "country", "year_week"])
    assert (totals["value"].sum() == totals["total"].first()).all()


def test_output_types():
    df = pv.get_detections()
    assert set(df["indicator"]) == {"detections"}
    assert set(df["unit"]) == {"count"}
    assert set(df["age"]) == {"total"}
    assert str(df["value"].dtype) == "Int64"
    assert str(df["total"].dtype) == "Int64"
    assert str(df["share"].dtype) == "float64"
    assert str(df["date"].dtype) == "datetime64[ns]"
    assert df.loc[df["country"] == "Italy", "country_code"].eq("IT").all()


# --- filters ----------------------------------------------------------------


def test_defaults_cover_influenza_rsv_and_both_settings():
    df = pv.get_detections()
    assert set(df["pathogen"]) == {"Influenza", "RSV"}
    assert set(df["setting"]) == {"primary care", "hospital"}
    assert set(df["country"]) == {"Italy", "Malta", "Spain"}


def test_setting_and_week_filters():
    df = pv.get_detections(setting="hospital")
    assert categories(df) == [("A", 30, 1 / 3, 90), ("B", 60, 2 / 3, 90)]
    assert set(pv.get_detections(start="2024-W51")["year_week"]) == {"2024-W51", "2025-W02"}
    assert pv.get_detections(season="2023/24").empty


@pytest.mark.parametrize(
    "kwargs, error, message",
    [
        ({"pathogen": "covid"}, InvalidParameterError, "not split by type"),
        ({"pathogen": ["flu", "sars-cov-2"]}, InvalidParameterError, "not split by type"),
        ({"pathogen": "measles"}, InvalidParameterError, "Unknown pathogen"),
        ({"level": "lineage"}, InvalidParameterError, "Unknown level"),
        ({"setting": "icu"}, InvalidParameterError, "Unknown setting"),
        ({"countries": "Sweden"}, DataNotFoundError, r"list_countries\('positivity'\)"),
    ],
)
def test_invalid_arguments(kwargs, error, message):
    with pytest.raises(error, match=message):
        pv.get_detections(**kwargs)


# --- as_of ------------------------------------------------------------------


def test_as_of_adds_vintage(monkeypatch):
    def load_as_of(file_name, as_of):
        df = frame(FILES[file_name])
        df["vintage"] = pd.Timestamp("2025-01-10")
        df.loc[df["yearweek"] == "2024-W50", "vintage"] = pd.NaT
        return df

    monkeypatch.setattr(api, "load_as_of", load_as_of)
    df = pv.get_detections("flu", "primary care", "Italy", as_of="2025-01-10")
    assert list(df.columns) == [*[c for c in api.DETECTION_COLUMNS if c != "subtype"], "vintage"]
    assert df.groupby("year_week")["vintage"].first().to_dict() == {
        "2024-W50": pd.NaT,
        "2024-W51": pd.Timestamp("2025-01-10"),
    }
