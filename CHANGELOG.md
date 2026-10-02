# Changelog

All notable changes to pyerviss are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 0.1.1

### Added

- `indicator` column (`"ili"`, `"ari"` or `"sari"`) as the first column of every query
  result, so results from different indicators stay distinguishable when combined with
  `pd.concat`.
- Documentation site at https://pyerviss.readthedocs.io: quickstart, querying, units and
  denominators, data sources, caching, and an API reference generated from docstrings.
- Full parameter, return and exception documentation on `get_ili`, `get_ari` and
  `get_sari` (previously they only pointed to `get_data`), visible in `help()` and the
  API reference.
- `Documentation` link in the package metadata, and PyPI and docs badges in the README.

### Changed

- Query results have a new first column, `indicator`. Code that selects columns by
  position needs updating; code that selects them by name is unaffected.

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
