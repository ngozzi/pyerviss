# PyERVISS: Status and Roadmap

Unofficial Python API for ERVISS (European Respiratory Virus Surveillance Summary) data:
ILI, ARI and SARI rates. Not affiliated with ECDC.

The README documents usage and units; the code and its tests are the reference for
behavior. This file tracks what is done and what is next.

## Status

**v0.1.0 released on [PyPI](https://pypi.org/project/pyerviss/)** (`pip install pyerviss`).

| Area | State |
|------|-------|
| Data mirror | `data/ILIARIRates.csv`, `data/SARIRates.csv`, `data/metadata.json` |
| Coverage | ILI/ARI from 2014-W40 (total age only before 2022-W25), SARI from 2022-W25 |
| Daily sync | `.github/workflows/sync-ecdc-data.yml` + `scripts/sync_ecdc.py`, 18:17 UTC |
| Library | `get_ili/get_ari/get_sari/get_data`, `coverage`, `list_countries`, `list_seasons`, `latest_week`, cache with hourly ETag checks |
| CI | `.github/workflows/ci.yml`: ruff, mypy, pytest on Python 3.10–3.12 |
| Releases | `.github/workflows/publish.yml`: a GitHub release `vX.Y.Z` publishes to PyPI (trusted publishing) |

## Next

### Documentation on Read the Docs
- [x] Tool: Sphinx + MyST (Markdown pages) + Furo theme; API reference from the
      Google-style docstrings (autodoc + napoleon)
- [x] Pages: installation and quickstart; querying (countries, weeks, seasons, age groups);
      output format; **units and denominators** (per-country table, Slovakia ICU note,
      comparability caveat); data sources, sync and history (ECDC, RespiCast import,
      retained rows); caching and offline use; API reference generated from docstrings;
      disclaimer
- [x] `.readthedocs.yaml` and a `docs` optional dependency group
- [x] Build the docs in CI (fail on warnings) so they can't silently break
- [x] Docs link and badges in the README; `Documentation` URL in `pyproject.toml`
- [x] Import the project on readthedocs.org
- [ ] Release 0.1.1 so the PyPI page shows the Documentation link

### Maintenance
- [ ] Confirm the daily sync works on GitHub: it has not run yet (first scheduled run
      2026-10-02 18:17 UTC), and the first run that finds new ECDC data is the first
      test of the bot committing to `main`
- [ ] Single-source the version: `__version__` in `src/pyerviss/__init__.py` duplicates
      `pyproject.toml`, and the release check only compares the tag with `pyproject.toml`.
      Read it with `importlib.metadata.version("pyerviss")` instead
- [x] Add a `CHANGELOG.md` (Keep a Changelog); use it for release notes
- [ ] Test on Python 3.13 in CI and add the classifier
- [ ] Delete merged branches on GitHub

### Later
- [ ] More ERVISS datasets (e.g. virus detections, flu subtypes). A new indicator is an
      entry in `src/pyerviss/indicators/__init__.py`, plus syncing its file in
      `scripts/sync_ecdc.py` (`FILES`), with units checked against ECDC's notes
- [ ] Snapshots (deferred): ECDC publishes dated snapshots since 2023-11-24, useful for
      reproducing what was known at a given date (e.g. forecast evaluation)

## Decisions

Recorded here so they aren't re-litigated.

- **Mirror, don't proxy:** the package downloads from this repo, not ECDC. The repo keeps
  rows ECDC later removes (cumulative merge keyed on country, week, indicator, age; ECDC
  values win on overlap).
- **Storage:** CSV in ECDC's column layout, deterministic sort and number formatting so
  git diffs show real revisions only. No data ships in the pip package.
- **Units:** every value is per 100,000 of its denominator. ECDC's per-100 series are
  multiplied by 1000 in the sync: ILI/ARI for Cyprus, Luxembourg, Malta (consultations);
  SARI for Greece, Ireland, Latvia, Luxembourg (hospital admissions). Finland ILI/ARI is
  per 100,000 consultations; Slovakia SARI counts ICU admissions only. The sync fails if a
  country's values shift by more than 100x, which signals a unit change upstream.
- **History:** ILI/ARI total-age history from 2014-W40 imported once from RespiCast's
  2024-10-11 ERVISS snapshots (`scripts/import_respicast.py`), filling gaps only; Malta
  ARI 2014–2015 (all zeros) dropped as missing data.
- **Weeks and seasons:** `date` is the Sunday ending the ISO week (RespiCast `truth_date`);
  a season "2024/25" runs 2024-W40 to 2025-W39.
- **Output:** long format, snake_case columns `indicator, country, country_code,
  year_week, date, age, value, denominator`; ISO2 country codes. `indicator` makes
  combined results (`pd.concat`) safe.
- **Releases:** record changes under "Unreleased" in `CHANGELOG.md` as they are merged.
  To release: rename "Unreleased" to the version and date, bump `version` in
  `pyproject.toml`, merge, and publish a GitHub release tagged `vX.Y.Z` with that
  section as its notes. Versions can never be re-uploaded to PyPI.
