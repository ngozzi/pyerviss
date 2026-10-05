"""Tests for the public API, on small sample files instead of downloaded data."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import pyerviss as pv
from pyerviss import api
from pyerviss.exceptions import DataNotFoundError, InvalidParameterError

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLES = {
    "ILIARIRates.csv": "sample_ili_ari.csv",
    "SARIRates.csv": "sample_sari.csv",
    "sentinelTestsDetectionsPositivity.csv": "sample_sentinel_virology.csv",
    "SARITestsDetectionsPositivity.csv": "sample_sari_virology.csv",
}


@pytest.fixture(autouse=True)
def sample_data(monkeypatch):
    def load_csv(file_name: str) -> pd.DataFrame:
        # Same types as the real loader: text everywhere except value
        df = pd.read_csv(FIXTURES / SAMPLES[file_name], dtype=str, keep_default_na=False)
        df["value"] = df["value"].astype("float64")
        return df

    monkeypatch.setattr(api, "load_csv", load_csv)


def rows(df: pd.DataFrame, *columns: str) -> list[tuple]:
    return list(df[list(columns)].itertuples(index=False, name=None))


# --- output format ----------------------------------------------------------


def test_output_columns_and_types():
    df = pv.get_ili(countries="Malta")
    assert list(df.columns) == api.COLUMNS
    assert df.iloc[0].to_dict() == {
        "indicator": "ili",
        "country": "Malta",
        "country_code": "MT",
        "year_week": "2024-W40",
        "date": pd.Timestamp("2024-10-06"),
        "age": "total",
        "value": 4200.0,
        "unit": "per 100,000 consultations",
    }
    assert str(df["date"].dtype) == "datetime64[ns]"
    assert str(df["value"].dtype) == "float64"


def test_date_is_sunday_including_53_week_years():
    df = pv.get_ili(countries="Greece")
    assert rows(df, "year_week", "date") == [("2020-W53", pd.Timestamp("2021-01-03"))]


def test_sorted_by_country_date_and_age_order():
    df = pv.get_ili(countries=["Italy", "Austria"], season="2024/25")
    assert rows(df, "country", "year_week", "age") == [
        ("Italy", "2024-W40", "0-4"),
        ("Italy", "2024-W40", "65+"),
        ("Italy", "2024-W40", "total"),
        ("Italy", "2025-W39", "total"),
    ]
    assert df.index.tolist() == [0, 1, 2, 3]


def test_unit_per_country():
    df = pv.get_ili(start="2024-W40", end="2024-W40")
    by_country = dict(rows(df.drop_duplicates("country"), "country", "unit"))
    assert by_country == {
        "Finland": "per 100,000 consultations",
        "Italy": "per 100,000 population",
        "Malta": "per 100,000 consultations",
    }


def test_sari_unit_per_country():
    df = pv.get_sari(age_groups="total").drop_duplicates("country")
    assert dict(rows(df, "country", "unit")) == {
        "Ireland": "per 100,000 hospital admissions",
        "Malta": "per 100,000 population",
        "Spain": "per 100,000 population",
    }


@pytest.mark.parametrize("name", ["ili", "ari", "sari"])
def test_indicator_column(name):
    df = pv.get_data(name)
    assert not df.empty
    assert set(df["indicator"]) == {name}


def test_combined_results_stay_distinguishable():
    both = pd.concat([pv.get_ili(countries="Italy"), pv.get_ari(countries="Italy")])
    totals = both[(both["year_week"] == "2024-W40") & (both["age"] == "total")]
    assert dict(rows(totals, "indicator", "value")) == {"ili": 363.0, "ari": 1100.0}


def test_indicators_are_separated():
    assert rows(pv.get_ari(countries="Italy"), "value") == [(1100.0,)]
    assert 1100.0 not in pv.get_ili(countries="Italy")["value"].tolist()


def test_empty_result_keeps_columns():
    df = pv.get_ili(countries="Malta", season="2015/16")
    assert df.empty
    assert list(df.columns) == api.COLUMNS


# --- countries --------------------------------------------------------------


@pytest.mark.parametrize("countries", ["Italy", "italy", "IT", "it", " Italy ", ["IT"]])
def test_country_by_name_or_code(countries):
    assert set(pv.get_ili(countries=countries)["country"]) == {"Italy"}


def test_multiple_countries_mixing_names_and_codes():
    assert set(pv.get_ili(countries=["MT", "Italy"])["country"]) == {"Italy", "Malta"}


def test_country_aliases():
    assert set(pv.get_ili(countries="EL")["country"]) == {"Greece"}


def test_unknown_country_suggests_close_match():
    with pytest.raises(InvalidParameterError, match="did you mean 'Italy'"):
        pv.get_ili(countries="Itly")
    with pytest.raises(InvalidParameterError, match="did you mean 'Czechia'"):
        pv.get_ili(countries="Czech Republik")


def test_unknown_country_without_close_match():
    with pytest.raises(InvalidParameterError, match=r"^Unknown country 'xyz'$"):
        pv.get_ili(countries="xyz")


def test_known_country_without_data_for_indicator():
    with pytest.raises(DataNotFoundError, match="Sweden has no ILI data"):
        pv.get_ili(countries="Sweden")
    assert set(pv.get_ari(countries="SE")["country"]) == {"Sweden"}


@pytest.mark.parametrize("countries", [[], 42, [None]])
def test_invalid_countries_argument(countries):
    with pytest.raises(InvalidParameterError, match="countries must be"):
        pv.get_ili(countries=countries)


# --- weeks and seasons ------------------------------------------------------


@pytest.mark.parametrize(
    "start, end",
    [
        ("2024-W40", "2025-W39"),
        ("2024-09-30", "2025-09-28"),  # Monday of W40 to Sunday of W39
        (date(2024, 10, 6), date(2025, 9, 22)),
    ],
)
def test_start_end_inclusive_in_any_format(start, end):
    df = pv.get_ili(countries="Italy", start=start, end=end, age_groups="total")
    assert rows(df, "year_week") == [("2024-W40",), ("2025-W39",)]


def test_open_ended_ranges():
    assert pv.get_ili(countries="Italy", start="2025-W40")["year_week"].tolist() == ["2025-W40"]
    assert pv.get_ili(end="2015-W01")["year_week"].tolist() == ["2014-W40"]


def test_start_after_end_rejected():
    with pytest.raises(InvalidParameterError, match="after end"):
        pv.get_ili(start="2025-W01", end="2024-W01")


def test_season_runs_w40_to_w39():
    df = pv.get_ili(countries="Italy", season="2024/25", age_groups="total")
    assert rows(df, "year_week") == [("2024-W40",), ("2025-W39",)]


def test_season_with_week_53():
    assert pv.get_ili(season="2020/21")["year_week"].tolist() == ["2020-W53"]


def test_multiple_seasons():
    df = pv.get_ili(countries="Italy", season=["2023/24", "2025/26"])
    assert rows(df, "year_week") == [("2024-W39",), ("2025-W40",)]


def test_season_and_dates_are_exclusive():
    with pytest.raises(InvalidParameterError, match="either season or start/end"):
        pv.get_ili(season="2024/25", end="2025-W01")


@pytest.mark.parametrize("kwargs", [{"season": "2024-25"}, {"start": "yesterday"}])
def test_malformed_weeks_and_seasons(kwargs):
    with pytest.raises(InvalidParameterError):
        pv.get_ili(**kwargs)


# --- age groups -------------------------------------------------------------


def test_age_group_filter():
    assert set(pv.get_ili(age_groups="65+")["age"]) == {"65+"}
    assert set(pv.get_ili(age_groups=["0-4", "65+"])["age"]) == {"0-4", "65+"}


def test_unknown_age_group():
    with pytest.raises(InvalidParameterError, match="Unknown age group"):
        pv.get_ili(age_groups="65-")


# --- indicators -------------------------------------------------------------


@pytest.mark.parametrize("name", ["ili", "ILI", "Ili"])
def test_get_data_indicator_name_case_insensitive(name):
    pd.testing.assert_frame_equal(pv.get_data(name), pv.get_ili())


def test_unknown_indicator():
    with pytest.raises(InvalidParameterError, match="available: ili, ari, sari"):
        pv.get_data("covid")


# --- discovery helpers ------------------------------------------------------


def test_coverage():
    cov = pv.coverage("ili")
    italy = cov[cov["country"] == "Italy"].iloc[0].to_dict()
    assert italy == {
        "country": "Italy",
        "country_code": "IT",
        "first_week": "2024-W39",
        "last_week": "2025-W40",
        "n_weeks": 4,
        "age_groups": ["0-4", "65+", "total"],
        "unit": "per 100,000 population",
    }
    assert cov["country"].tolist() == ["Austria", "Finland", "Greece", "Italy", "Malta"]


def test_list_countries():
    assert pv.list_countries("sari") == ["Ireland", "Malta", "Spain"]
    assert pv.list_countries("ari") == ["Italy", "Sweden"]


def test_list_seasons():
    assert pv.list_seasons("sari") == ["2024/25", "2025/26"]
    assert pv.list_seasons() == [
        "2014/15",
        "2020/21",
        "2023/24",
        "2024/25",
        "2025/26",
    ]


def test_latest_week():
    assert pv.latest_week("ili") == "2025-W40"
    assert pv.latest_week() == "2026-W38"


def test_public_exports():
    assert set(pv.__all__) == {
        "__version__",
        "add_positivity_ci",
        "add_season_week",
        "clear_cache",
        "coverage",
        "get_ari",
        "get_data",
        "get_ili",
        "get_positivity",
        "get_sari",
        "latest_week",
        "list_countries",
        "list_seasons",
        "plot_seasons",
        "update_data",
    }


# --- positivity -------------------------------------------------------------


def test_positivity_output():
    df = pv.get_positivity(pathogen="influenza", setting="primary care", countries="Italy")
    assert list(df.columns) == api.POSITIVITY_COLUMNS
    assert df.iloc[0].to_dict() == {
        "indicator": "positivity",
        "setting": "primary care",
        "pathogen": "Influenza",
        "country": "Italy",
        "country_code": "IT",
        "year_week": "2024-W50",
        "date": pd.Timestamp("2024-12-15"),
        "age": "total",
        "value": 32.1,
        "unit": "%",
        "tests": 184,
        "detections": 59,
    }
    assert str(df["tests"].dtype) == "Int64"


def test_positivity_excludes_subtypes_and_weeks_without_positivity():
    df = pv.get_positivity(pathogen="influenza", setting="primary care", countries="IT")
    # Subtype detections (A(H3), A(H1)pdm09) and 2024-W51 (0 tests, no positivity) are out
    assert rows(df, "year_week", "value") == [("2024-W50", 32.1)]


def test_positivity_defaults_to_all_pathogens_and_settings():
    df = pv.get_positivity()
    assert rows(df, "setting", "pathogen", "country") == [
        ("hospital", "Influenza", "Spain"),
        ("primary care", "Influenza", "EU/EEA"),
        ("primary care", "Influenza", "Italy"),
        ("primary care", "RSV", "Italy"),
        ("primary care", "SARS-CoV-2", "Malta"),
    ]


@pytest.mark.parametrize(
    "pathogen, expected",
    [
        ("RSV", {"RSV"}),
        ("rsv", {"RSV"}),
        ("covid", {"SARS-CoV-2"}),
        ("SARS-CoV-2", {"SARS-CoV-2"}),
        ("flu", {"Influenza"}),
        (["influenza", "rsv"], {"Influenza", "RSV"}),
    ],
)
def test_positivity_pathogen_names(pathogen, expected):
    assert set(pv.get_positivity(pathogen=pathogen)["pathogen"]) == expected


@pytest.mark.parametrize("setting", ["hospital", "Hospital", ["hospital"]])
def test_positivity_setting(setting):
    assert set(pv.get_positivity(setting=setting)["setting"]) == {"hospital"}


def test_positivity_eu_aggregate():
    for name in ["EU/EEA", "EU", "eu"]:
        df = pv.get_positivity(countries=name)
        assert rows(df, "country", "country_code", "tests") == [("EU/EEA", "EU", 5000)]


def test_positivity_keeps_counts_for_small_samples():
    df = pv.get_positivity(pathogen="covid")
    assert rows(df, "value", "tests", "detections") == [(100.0, 1, 1)]


def test_positivity_week_filters():
    assert pv.get_positivity(season="2023/24").empty
    assert len(pv.get_positivity(start="2025-01-01")) == 1  # Spain hospital, 2025-W02
    with pytest.raises(InvalidParameterError, match="either season or start/end"):
        pv.get_positivity(season="2024/25", start="2024-W40")


@pytest.mark.parametrize(
    "kwargs, error, message",
    [
        ({"pathogen": "measles"}, InvalidParameterError, "Unknown pathogen"),
        ({"setting": "icu"}, InvalidParameterError, "Unknown setting"),
        ({"countries": "Itly"}, InvalidParameterError, "did you mean 'Italy'"),
        ({"countries": "Sweden"}, DataNotFoundError, "Sweden has no positivity data"),
        # Malta reports SARS-CoV-2 positivity but not influenza
        ({"countries": "MT", "pathogen": "flu"}, DataNotFoundError, "Malta has no positivity"),
    ],
)
def test_positivity_invalid_arguments(kwargs, error, message):
    with pytest.raises(error, match=message):
        pv.get_positivity(**kwargs)


def test_positivity_discovery():
    assert pv.list_countries("positivity") == ["EU/EEA", "Italy", "Malta", "Spain"]
    assert pv.list_seasons("positivity") == ["2024/25"]
    assert pv.latest_week("positivity") == "2025-W02"
    cov = pv.coverage("positivity")
    assert list(cov.columns) == [
        "setting",
        "pathogen",
        "country",
        "country_code",
        "first_week",
        "last_week",
        "n_weeks",
        "unit",
    ]
    italy_rsv = cov[(cov["country"] == "Italy") & (cov["pathogen"] == "RSV")].iloc[0]
    assert (italy_rsv["setting"], italy_rsv["n_weeks"], italy_rsv["unit"]) == (
        "primary care",
        1,
        "%",
    )


def test_unknown_indicator_in_discovery_mentions_positivity():
    with pytest.raises(InvalidParameterError, match="ili, ari, sari, positivity"):
        pv.list_countries("covid")


def test_rates_and_positivity_concatenate():
    both = pd.concat([pv.get_ili(countries="Italy"), pv.get_positivity(countries="Italy")])
    assert set(both["indicator"]) == {"ili", "positivity"}
    assert both[both["indicator"] == "ili"]["setting"].isna().all()
