"""Season overlay plots. Requires matplotlib: ``pip install "pyerviss[plot]"``."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, cast, overload

import numpy as np
import pandas
import pandas as pd

from .exceptions import InvalidParameterError
from .transforms import add_season_week
from .types import AGE_GROUPS
from .utils import parse_season

if TYPE_CHECKING:
    # Full names, so the API reference links them to matplotlib's documentation
    import matplotlib.axes
    import matplotlib.figure

# Highlighted seasons, most recent first. The first three slots of a palette validated
# for colour-vision deficiency on all pairs; at most three seasons can be highlighted.
HIGHLIGHT_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]
CONTEXT_COLOR = "#bdbcb6"  # other seasons
TEXT_COLOR = "#52514e"
GRID_COLOR = "#e8e7e3"

# Columns that identify one weekly series; facet splits on one of them
SERIES_COLUMNS = ["indicator", "setting", "pathogen", "country", "age"]
FACETS = {"age": "age", "country": "country"}
MAX_COLUMNS = 4

# Evenly spaced ticks, as season weeks of a 52-week season (W40 is week 1, W01 week 14)
_TICKS = [(1, "W40"), (14, "W01"), (27, "W14"), (40, "W27")]
_INDICATOR_LABELS = {"ili": "ILI", "ari": "ARI", "sari": "SARI", "positivity": "Positivity"}


@overload
def plot_seasons(
    df: pandas.DataFrame,
    highlight: str | Iterable[str] | None = ...,
    facet: None = ...,
    sharey: bool = ...,
    ax: matplotlib.axes.Axes | None = ...,
) -> matplotlib.axes.Axes: ...


@overload
def plot_seasons(
    df: pandas.DataFrame,
    highlight: str | Iterable[str] | None = ...,
    *,
    facet: str,
    sharey: bool = ...,
    ax: matplotlib.axes.Axes | None = ...,
) -> matplotlib.figure.Figure: ...


@overload
def plot_seasons(
    df: pandas.DataFrame,
    highlight: str | Iterable[str] | None,
    facet: str,
    sharey: bool = ...,
    ax: matplotlib.axes.Axes | None = ...,
) -> matplotlib.figure.Figure: ...


def plot_seasons(
    df: pandas.DataFrame,
    highlight: str | Iterable[str] | None = None,
    facet: str | None = None,
    sharey: bool = False,
    ax: matplotlib.axes.Axes | None = None,
) -> matplotlib.axes.Axes | matplotlib.figure.Figure:
    """Plot one line per season, aligned on the week of the season (W40 to W39).

    Past seasons are drawn in grey for context; highlighted seasons in colour. If ``df``
    has ``ci_low`` and ``ci_high`` columns (see ``add_positivity_ci``), the interval is
    drawn as a band around highlighted seasons. Weeks without data are left as gaps.

    Args:
        df: A result of ``get_ili``, ``get_ari``, ``get_sari`` or ``get_positivity``.
            Without ``facet`` it must contain a single series: one indicator, country
            and age group (and, for positivity, one pathogen and setting).
        highlight: Season(s) to draw in colour, e.g. "2024/25" or ["2023/24",
            "2024/25"] (at most three). Default: the most recent season in ``df``.
        facet: "country" or "age" to draw one panel per country or age group. Every
            other column must then have a single value.
        sharey: Use the same y-axis range in all panels (facets only). Only allowed when
            all panels have the same unit.
        ax: Matplotlib axes to draw on (without facet only). Default: a new figure.

    Returns:
        The matplotlib ``Axes`` without facet, or the ``Figure`` with facets.

    Raises:
        InvalidParameterError: ``df`` is empty or has several series, an invalid
            highlight, facet or sharey, or ``ax`` combined with ``facet``.
        ImportError: matplotlib is not installed.
    """
    plt = _import_pyplot()
    df = _validate(df)
    facet_column = _resolve_facet(facet)
    if facet_column is None and sharey:
        raise InvalidParameterError("sharey only applies with facet")
    if facet_column is not None and ax is not None:
        raise InvalidParameterError("ax cannot be combined with facet")

    df = add_season_week(df)
    seasons = _resolve_highlight(highlight, df)
    ordered = sorted(seasons, reverse=True)  # most recent season gets the first colour
    colors = dict(zip(ordered, HIGHLIGHT_COLORS[: len(ordered)], strict=True))

    if facet_column is None:
        _require_single_series(df, exclude=None)
        if ax is None:
            _, ax = plt.subplots(figsize=(8, 4.5), layout="constrained")
        _draw_panel(ax, df, colors)
        ax.set_title(_series_title(df), loc="left", color="black")
        ax.set_ylabel(_axis_label(df), color=TEXT_COLOR)
        ax.legend(handles=_legend_handles(df, colors), **_LEGEND_STYLE)
        return ax

    _require_single_series(df, exclude=facet_column)
    panels = _panel_order(df, facet_column)
    units = {key: _unit(df[df[facet_column] == key]) for key in panels}
    if sharey and len(set(units.values())) > 1:
        raise InvalidParameterError(
            "sharey=True needs the same unit in every panel; got "
            + ", ".join(sorted(set(units.values())))
        )

    # Roughly square grids (4 panels -> 2x2), at most MAX_COLUMNS wide
    ncols = min(MAX_COLUMNS, math.ceil(math.sqrt(len(panels))))
    nrows = math.ceil(len(panels) / ncols)
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(3.6 * ncols, 2.8 * nrows),
        sharex=True,
        sharey=sharey,
        squeeze=False,
        layout="constrained",
    )
    flat = axes.ravel()
    mixed_units = len(set(units.values())) > 1
    for panel_ax, key in zip(flat[: len(panels)], panels, strict=True):
        _draw_panel(panel_ax, df[df[facet_column] == key], colors)
        title = f"{key} ({units[key]})" if mixed_units else str(key)
        panel_ax.set_title(title, loc="left", fontsize="medium", color="black")
    for unused in flat[len(panels) :]:
        unused.set_visible(False)
    # With shared x-axes only the bottom row shows tick labels; label the lowest
    # visible panel of each column instead, since trailing grid cells are hidden
    for column in range(ncols):
        visible = [row for row in range(nrows) if row * ncols + column < len(panels)]
        axes[visible[-1], column].xaxis.set_tick_params(labelbottom=True)
    if not mixed_units:
        for row in axes:
            row[0].set_ylabel(_axis_label(df), color=TEXT_COLOR)
    fig.suptitle(_series_title(df, exclude=facet_column), x=0.01, ha="left")
    fig.legend(
        handles=_legend_handles(df, colors),
        loc="outside upper right",
        ncols=len(colors) + 1,
        **_LEGEND_STYLE,
    )
    return cast("matplotlib.figure.Figure", fig)


# --- helpers ----------------------------------------------------------------


def _import_pyplot() -> Any:
    try:
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise ImportError('Plotting requires matplotlib: pip install "pyerviss[plot]"') from error
    return plt


def _validate(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        raise InvalidParameterError("plot_seasons expects a DataFrame from a pyerviss query")
    missing = [c for c in ["indicator", "country", "year_week", "value", "unit"] if c not in df]
    if missing:
        raise InvalidParameterError(
            f"df is missing column(s) {missing}; pass a result of a pyerviss query"
        )
    if df.empty:
        raise InvalidParameterError("df is empty: nothing to plot")
    return df


def _resolve_facet(facet: str | None) -> str | None:
    if facet is None:
        return None
    key = facet.lower() if isinstance(facet, str) else facet
    if key not in FACETS:
        raise InvalidParameterError(
            f"Unknown facet {facet!r}; available: {', '.join(map(repr, FACETS))}"
        )
    return FACETS[key]


def _resolve_highlight(highlight: str | Iterable[str] | None, df: pd.DataFrame) -> list[str]:
    if highlight is None:
        return [str(df["season"].max())]
    seasons = [highlight] if isinstance(highlight, str) else list(highlight)
    if not seasons or len(seasons) > len(HIGHLIGHT_COLORS):
        raise InvalidParameterError(
            f"highlight takes 1 to {len(HIGHLIGHT_COLORS)} seasons, got {len(seasons)}"
        )
    normalized = []
    for season in seasons:
        first, _ = parse_season(season)  # validates the format
        start_year = int(first[:4])
        normalized.append(f"{start_year}/{(start_year + 1) % 100:02d}")
    return list(dict.fromkeys(normalized))


def _require_single_series(df: pd.DataFrame, exclude: str | None) -> None:
    for column in SERIES_COLUMNS:
        if column == exclude or column not in df:
            continue
        values = df[column].dropna().unique()
        if len(values) > 1:
            shown = ", ".join(map(str, sorted(values)[:5])) + (", ..." if len(values) > 5 else "")
            hint = {
                "age": 'filter with age_groups="total" (or another group), or use facet="age"',
                "country": 'filter to one country, or use facet="country"',
            }.get(column, f"filter to one {column}")
            raise InvalidParameterError(
                f"df has {len(values)} values of {column} ({shown}); plot_seasons draws one "
                f"series per panel. Fix: {hint}"
            )


def _panel_order(df: pd.DataFrame, column: str) -> list[str]:
    keys = list(pd.unique(df[column]))
    if column == "age":
        return [a for a in AGE_GROUPS if a in keys] + [a for a in keys if a not in AGE_GROUPS]
    return keys  # query results are sorted by country


def _draw_panel(ax: matplotlib.axes.Axes, df: pd.DataFrame, colors: dict[str, str]) -> None:
    max_week = int(df["season_week"].max())
    weeks = np.arange(1, max(max_week, 52) + 1)
    has_ci = {"ci_low", "ci_high"} <= set(df.columns)

    def series(season_df: pd.DataFrame, column: str) -> np.ndarray:
        # Reindex on every week so missing weeks become gaps, not interpolated lines
        values = season_df.set_index("season_week")[column].astype("float64")
        return np.asarray(values.reindex(weeks), dtype="float64")

    for season, season_df in df.groupby("season", sort=True):
        if season not in colors:
            ax.plot(weeks, series(season_df, "value"), color=CONTEXT_COLOR, linewidth=1)
    for season in sorted(colors):  # highlighted seasons on top
        season_df = df[df["season"] == season]
        if season_df.empty:
            ax.text(
                0.98,
                0.95,
                f"no data for {season}",
                transform=ax.transAxes,
                ha="right",
                va="top",
                fontsize="small",
                color=TEXT_COLOR,
            )
            continue
        if has_ci:
            ax.fill_between(
                weeks,
                series(season_df, "ci_low"),
                series(season_df, "ci_high"),
                color=colors[season],
                alpha=0.18,
                linewidth=0,
            )
        ax.plot(
            weeks,
            series(season_df, "value"),
            color=colors[season],
            linewidth=2,
            solid_capstyle="round",
            label=season,
        )

    ax.set_xlim(1, weeks[-1])
    ax.set_xticks([w for w, _ in _TICKS], [label for _, label in _TICKS])
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", color=GRID_COLOR, linewidth=1)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID_COLOR)
    ax.tick_params(colors=TEXT_COLOR, labelcolor=TEXT_COLOR)


_LEGEND_STYLE: dict[str, Any] = {"frameon": False, "fontsize": "small", "labelcolor": TEXT_COLOR}


def _legend_handles(df: pd.DataFrame, colors: dict[str, str]) -> list[Any]:
    from matplotlib.lines import Line2D

    handles = [
        Line2D([], [], color=colors[s], linewidth=2, label=s) for s in sorted(colors, reverse=True)
    ]
    if (~df["season"].isin(list(colors))).any():
        handles.append(Line2D([], [], color=CONTEXT_COLOR, linewidth=1, label="other seasons"))
    return handles


def _unit(df: pd.DataFrame) -> str:
    return " / ".join(map(str, pd.unique(df["unit"].dropna())))


def _axis_label(df: pd.DataFrame) -> str:
    if (df["indicator"] == "positivity").all():
        return "% of tests positive"
    return _unit(df)


def _series_title(df: pd.DataFrame, exclude: str | None = None) -> str:
    indicator = str(df["indicator"].iloc[0])
    title = _INDICATOR_LABELS.get(indicator, indicator)
    if indicator == "positivity":
        title = f"{df['pathogen'].iloc[0]} positivity ({df['setting'].iloc[0]})"
    parts = [title]
    if exclude != "country":
        parts.append(str(df["country"].iloc[0]))
    if exclude != "age" and "age" in df and df["age"].iloc[0] != "total":
        parts.append(f"age {df['age'].iloc[0]}")
    return ", ".join(parts)
