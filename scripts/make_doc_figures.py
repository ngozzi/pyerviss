"""Regenerate the figures in docs/_static/plotting from the current data.

Usage:
    python scripts/make_doc_figures.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from matplotlib.axes import Axes  # noqa: E402

import pyerviss as pv  # noqa: E402

OUT = Path(__file__).parent.parent / "docs" / "_static" / "plotting"
DPI = 100


def save(ax: Axes, name: str) -> None:
    ax.get_figure(root=True).savefig(OUT / name, dpi=DPI)  # type: ignore[union-attr]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    save(pv.plot_seasons(pv.get_ili(countries="Italy", age_groups="total")), "seasons.png")

    ili = pv.get_ili(countries=["Belgium", "France", "Spain", "Malta"], age_groups="total")
    pv.plot_seasons(ili, facet="country").savefig(OUT / "facet_country.png", dpi=DPI)

    pv.plot_seasons(pv.get_ili(countries="Belgium"), facet="age").savefig(
        OUT / "facet_age.png", dpi=DPI
    )

    positivity = pv.get_positivity(pathogen="influenza", setting="primary care", countries="IT")
    ax = pv.plot_seasons(pv.add_positivity_ci(positivity), highlight=["2023/24", "2024/25"])
    save(ax, "positivity_ci.png")
    print(f"Figures written to {OUT}")


if __name__ == "__main__":
    main()
