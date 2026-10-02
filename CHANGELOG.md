# Changelog

All notable changes to pyerviss are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 0.1.1

### Added

- `get_positivity`: weekly influenza, RSV and SARS-CoV-2 test positivity in primary care
  (sentinel GPs) and hospitals (SARI), from 2022-W25, with the `tests` and `detections`
  counts it is computed from. Results add `setting` and `pathogen` columns.
- The EU/EEA aggregate published by ECDC, queryable as `"EU/EEA"` or `"EU"` (positivity).
- `coverage`, `list_countries`, `list_seasons` and `latest_week` accept `"positivity"`.
- Data: primary care and SARI virology files (tests, detections, positivity by pathogen,
  type and subtype) mirrored and synced daily from ECDC.

- `indicator` column (`"ili"`, `"ari"` or `"sari"`) as the first column of every query
  result, so results from different indicators stay distinguishable when combined with
  `pd.concat`.
- Documentation site at https://pyerviss.readthedocs.io: quickstart, querying, positivity,
  units, data sources, caching, and an API reference generated from docstrings.
- Full parameter, return and exception documentation on `get_ili`, `get_ari` and
  `get_sari` (previously they only pointed to `get_data`), visible in `help()` and the
  API reference.
- `Documentation` link in the package metadata, and PyPI and docs badges in the README.

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

[Unreleased]: https://github.com/ngozzi/pyerviss/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ngozzi/pyerviss/releases/tag/v0.1.0
