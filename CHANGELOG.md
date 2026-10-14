# Changelog

All notable changes to pyerviss are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-10-14

### Added

- `get_detections`: influenza and RSV detections by type (A, B; RSV-A, RSV-B) or
  subtype (A(H1)pdm09, A(H3), B/Victoria, B/Yamagata), with each category's share of
  the week's detections. Supports the usual filters and `as_of`. See the Positivity
  page.
- `as_of` argument for `get_ili`, `get_ari`, `get_sari`, `get_data`, `get_positivity`,
  `coverage` and `latest_week`: data as ECDC published it on a past date, from ECDC's
  weekly snapshots (from 2023-11-24; SARI from 2024-11-08), for backtesting forecasts
  without later revisions. Results get a `vintage` column. `list_vintages` lists the
  available dates. See the Past vintages page.
- `start_week` argument for `add_season_week` and `utils.season_of`, for seasons that
  don't start at W40.
- Longer history, recovered from earlier versions of ECDC's files in its git history:
  SARI rates and hospital positivity from 2020-W40 (previously 2022-W25), primary care
  positivity from 2014-W25 (previously 2022-W25), and ILI and ARI by age group from
  2014-W40 for most countries (previously `"total"` only before 2022-W25). See the Data
  sources page.

### Changed

- `plot_seasons` follows ERVISS's dashboard:
  - seasons run from W25 to W24, so the summer trough comes first and the autumn rise
    is fully visible; ticks are ISO weeks (25, 37, 49, 9, 21). `start_week=40` restores
    the previous W40 to W39 layout.
  - only the 3 most recent other seasons are drawn for context, in shades of grey
    (darker = more recent) and named in the legend. `past_seasons` changes the number;
    `past_seasons=None` draws every season in grey, as before.

## [0.2.0] - 2026-10-05

### Added

- `plot_seasons`: season overlay chart (one line per season, aligned W40 to W39), with
  the latest or chosen seasons highlighted, past seasons in grey, gaps for missing weeks,
  y-axis from `unit`, `facet="country"` or `facet="age"` for small multiples, and
  confidence bands for positivity. Requires matplotlib: `pip install "pyerviss[plot]"`.
- `add_season_week`: adds `season` and `season_week` columns, for plotting with any
  library.
- `add_positivity_ci`: adds a Wilson confidence interval (`ci_low`, `ci_high`) for
  positivity, computed from `tests` and `detections`.
- Documentation: Plotting page, and a quickstart notebook
  (`notebooks/quickstart.ipynb`) that opens in Google Colab.
- `py.typed` marker: type checkers (mypy, pyright) now use pyerviss's type hints;
  previously every pyerviss call was typed as `Any`.

## [0.1.1] - 2026-10-02

### Added

- `get_positivity`: weekly influenza, RSV and SARS-CoV-2 test positivity in primary care
  (sentinel GPs) and hospitals (SARI), from 2022-W25, with the `tests` and `detections`
  counts it is computed from. Results add `setting` and `pathogen` columns.
- The EU/EEA aggregate published by ECDC, queryable as `"EU/EEA"` or `"EU"` (positivity).
- `coverage`, `list_countries`, `list_seasons` and `latest_week` accept `"positivity"`.
- Data: primary care and SARI virology files (tests, detections, positivity by pathogen,
  type and subtype) mirrored and synced daily from ECDC.
- `indicator` column (`"ili"`, `"ari"`, `"sari"` or `"positivity"`) as the first column of
  every query result, so results from different indicators stay distinguishable when
  combined with `pd.concat`.
- Documentation site at https://pyerviss.readthedocs.io: quickstart, querying, positivity,
  units, data sources, caching, and an API reference generated from docstrings.
- Full parameter, return and exception documentation on `get_ili`, `get_ari` and
  `get_sari` (previously they only pointed to `get_data`), visible in `help()` and the
  API reference.
- `Documentation` and `Changelog` links in the package metadata, and PyPI and docs badges
  in the README.

### Changed

- **The `denominator` column is replaced by `unit`**, which states the full unit, e.g.
  `"per 100,000 population"`, `"per 100,000 consultations"`,
  `"per 100,000 hospital admissions"`, or `"%"` for positivity. `coverage()` likewise
  returns `unit`. Code using `denominator` needs updating; values map one-to-one.
- Query results have a new first column, `indicator`. Code that selects columns by
  position needs updating; code that selects them by name is unaffected.
- `pyerviss.__version__` is read from the installed package metadata, so the version is
  defined only in `pyproject.toml`.

## [0.1.0] - 2026-10-01

First release.

### Added

- `get_ili`, `get_ari`, `get_sari` and `get_data`: weekly rates as pandas DataFrames,
  filtered by country (name or ISO2 code), week or date range, season and age group.
- `coverage`, `list_countries`, `list_seasons` and `latest_week` to explore what is
  available.
- Local cache with hourly update checks and offline use; `update_data` and
  `clear_cache`.
- Data: ILI and ARI from 2014-W40, SARI from 2022-W25, synced daily from ECDC, with
  every value per 100,000 of its denominator.

[Unreleased]: https://github.com/ngozzi/pyerviss/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/ngozzi/pyerviss/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/ngozzi/pyerviss/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/ngozzi/pyerviss/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/ngozzi/pyerviss/releases/tag/v0.1.0
