"""Tests for pyerviss.plotting: checks what is drawn, not rendered images."""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from matplotlib.colors import to_hex  # noqa: E402

import pyerviss as pv  # noqa: E402
from pyerviss import plotting  # noqa: E402
from pyerviss.exceptions import InvalidParameterError  # noqa: E402

BLUE, ORANGE, AQUA = plotting.HIGHLIGHT_COLORS


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


def rates(
    seasons=("2022/23", "2023/24", "2024/25"),
    countries=("Italy",),
    ages=("total",),
    unit="per 100,000 population",
    indicator="ili",
):
    """Rate rows for every week from W40 to W20 of each season."""
    rows = []
    for season in seasons:
        start = int(season[:4])
        weeks = [f"{start}-W{w:02d}" for w in range(40, 53)]
        weeks += [f"{start + 1}-W{w:02d}" for w in range(1, 21)]
        for country in countries:
            for age in ages:
                for i, week in enumerate(weeks):
                    rows.append(
                        {
                            "indicator": indicator,
                            "country": country,
                            "country_code": country[:2].upper(),
                            "year_week": week,
                            "age": age,
                            "value": float(i),
                            "unit": unit if country != "Malta" else "per 100,000 consultations",
                        }
                    )
    return pd.DataFrame(rows)


def line_colors(ax):
    return [to_hex(line.get_color()) for line in ax.get_lines()]


# --- single series ----------------------------------------------------------


def test_returns_axes_with_context_and_highlight():
    ax = pv.plot_seasons(rates())
    colors = line_colors(ax)
    # Two past seasons in grey, the latest (2024/25) highlighted and drawn last
    assert colors == [plotting.CONTEXT_COLOR, plotting.CONTEXT_COLOR, BLUE]
    assert ax.get_title(loc="left") == "ILI, Italy"
    assert ax.get_ylabel() == "per 100,000 population"
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["2024/25", "other seasons"]


def test_weeks_are_aligned_on_season_week():
    ax = pv.plot_seasons(rates(seasons=("2024/25",)))
    x, y = ax.get_lines()[0].get_data()
    assert x[0] == 1 and y[0] == 0  # 2024-W40 is season week 1
    assert y[13] == 13  # 2025-W01 is season week 14


def test_missing_weeks_are_gaps_not_interpolated():
    df = rates(seasons=("2024/25",))
    df = df[df["year_week"] != "2024-W45"]
    _, y = pv.plot_seasons(df).get_lines()[0].get_data()
    assert np.isnan(y[5])  # 2024-W45 is season week 6
    assert np.isnan(y[-1])  # summer weeks without data


def test_highlight_order_and_colors():
    ax = pv.plot_seasons(rates(), highlight=["2022/23", "2024/25"])
    # Most recent highlighted season gets the first colour
    assert line_colors(ax) == [plotting.CONTEXT_COLOR, ORANGE, BLUE]
    assert [t.get_text() for t in ax.get_legend().get_texts()] == [
        "2024/25",
        "2022/23",
        "other seasons",
    ]


def test_highlight_accepts_long_season_format():
    ax = pv.plot_seasons(rates(), highlight="2023/2024")
    assert line_colors(ax).count(BLUE) == 1


def test_highlight_season_without_data_is_noted():
    ax = pv.plot_seasons(rates(), highlight="2025/26")
    assert "no data for 2025/26" in [t.get_text() for t in ax.texts]
    assert BLUE not in line_colors(ax)


@pytest.mark.parametrize(
    "highlight, message",
    [
        (["2021/22", "2022/23", "2023/24", "2024/25"], "1 to 3 seasons"),
        ([], "1 to 3 seasons"),
        ("2024-25", "Invalid season"),
    ],
)
def test_invalid_highlight(highlight, message):
    with pytest.raises(InvalidParameterError, match=message):
        pv.plot_seasons(rates(), highlight=highlight)


def test_draws_on_given_axes():
    _, ax = plt.subplots()
    assert pv.plot_seasons(rates(), ax=ax) is ax


def test_positivity_labels_and_ci_band():
    df = rates(seasons=("2023/24", "2024/25")).assign(
        indicator="positivity",
        setting="primary care",
        pathogen="Influenza",
        unit="%",
        tests=100,
        detections=30,
    )
    ax = pv.plot_seasons(pv.add_positivity_ci(df))
    assert ax.get_title(loc="left") == "Influenza positivity (primary care), Italy"
    assert ax.get_ylabel() == "% of tests positive"
    assert len(ax.collections) == 1  # one band, for the highlighted season only


def test_no_band_without_ci_columns():
    assert len(pv.plot_seasons(rates()).collections) == 0


@pytest.mark.parametrize(
    "df, message",
    [
        (rates(ages=("0-4", "total")), r"2 values of age .*facet=\"age\""),
        (rates(countries=("Italy", "Spain")), r"2 values of country .*facet=\"country\""),
        (pd.concat([rates(), rates(indicator="ari")]), "2 values of indicator"),
        (rates().iloc[0:0], "empty"),
        (rates().drop(columns="unit"), "missing column"),
    ],
)
def test_rejects_several_series_and_bad_input(df, message):
    with pytest.raises(InvalidParameterError, match=message):
        pv.plot_seasons(df)


# --- facets -----------------------------------------------------------------


def test_facet_country():
    fig = pv.plot_seasons(rates(countries=("Italy", "Spain", "France")), facet="country")
    visible = [ax for ax in fig.axes if ax.get_visible()]
    assert [ax.get_title(loc="left") for ax in visible] == ["Italy", "Spain", "France"]
    assert all(line_colors(ax)[-1] == BLUE for ax in visible)
    assert fig.get_suptitle() == "ILI"
    assert visible[0].get_ylabel() == "per 100,000 population"


def test_facet_age_order():
    fig = pv.plot_seasons(rates(ages=("total", "65+", "0-4")), facet="Age")
    visible = [ax for ax in fig.axes if ax.get_visible()]
    assert [ax.get_title(loc="left") for ax in visible] == ["0-4", "65+", "total"]
    assert fig.get_suptitle() == "ILI, Italy"


def test_facet_grid_hides_unused_cells_and_labels_columns():
    fig = pv.plot_seasons(rates(countries=("A1", "B1", "C1", "D1", "E1")), facet="country")
    assert len(fig.axes) == 6  # 2 rows x 3 columns
    assert sum(ax.get_visible() for ax in fig.axes) == 5
    # Column 3 has no visible panel in row 2, so its row-1 panel shows tick labels
    assert any(label.get_visible() for label in fig.axes[2].get_xticklabels())
    assert not any(label.get_visible() for label in fig.axes[0].get_xticklabels())


@pytest.mark.parametrize(
    "n, shape", [(1, (1, 1)), (2, (1, 2)), (4, (2, 2)), (9, (3, 3)), (26, (7, 4))]
)
def test_facet_grid_shape(n, shape):
    countries = tuple(f"C{i:02d}" for i in range(n))
    fig = pv.plot_seasons(rates(seasons=("2024/25",), countries=countries), facet="country")
    grid = fig.axes[0].get_subplotspec().get_gridspec()
    assert (grid.nrows, grid.ncols) == shape


def test_facet_mixed_units_in_titles():
    fig = pv.plot_seasons(rates(countries=("Italy", "Malta")), facet="country")
    titles = [ax.get_title(loc="left") for ax in fig.axes]
    assert titles == ["Italy (per 100,000 population)", "Malta (per 100,000 consultations)"]


def test_facet_sharey():
    fig = pv.plot_seasons(rates(countries=("Italy", "Spain")), facet="country", sharey=True)
    first, second = fig.axes
    assert first.get_ylim() == second.get_ylim()
    with pytest.raises(InvalidParameterError, match="same unit"):
        pv.plot_seasons(rates(countries=("Italy", "Malta")), facet="country", sharey=True)


def test_facet_still_requires_single_series_per_panel():
    with pytest.raises(InvalidParameterError, match="values of age"):
        pv.plot_seasons(rates(countries=("Italy", "Spain"), ages=("0-4", "total")), facet="country")


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"facet": "pathogen"}, "Unknown facet"),
        ({"sharey": True}, "sharey only applies with facet"),
    ],
)
def test_invalid_facet_options(kwargs, message):
    with pytest.raises(InvalidParameterError, match=message):
        pv.plot_seasons(rates(), **kwargs)


def test_facet_rejects_ax():
    _, ax = plt.subplots()
    with pytest.raises(InvalidParameterError, match="ax cannot be combined"):
        pv.plot_seasons(rates(countries=("Italy", "Spain")), facet="country", ax=ax)


def test_does_not_change_global_style():
    before = dict(matplotlib.rcParams)
    pv.plot_seasons(rates(countries=("Italy", "Spain")), facet="country")
    assert dict(matplotlib.rcParams) == before


def test_missing_matplotlib_gives_install_hint(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("matplotlib"):
            raise ImportError("No module named 'matplotlib'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ImportError, match=r'pip install "pyerviss\[plot\]"'):
        pv.plot_seasons(rates())
