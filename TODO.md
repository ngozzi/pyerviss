# PyERVISS: Status and Roadmap

Unofficial Python API for ERVISS (European Respiratory Virus Surveillance Summary) data:
ILI, ARI and SARI rates. Not affiliated with ECDC.

Usage, units and data sources are documented at https://pyerviss.readthedocs.io; the code
and its tests are the reference for behavior; `CHANGELOG.md` lists changes per release.
This file tracks what is done and what is next.

## Status

**On [PyPI](https://pypi.org/project/pyerviss/)** (`pip install pyerviss`): v0.1.0, with
v0.1.1 ready to publish (see `CHANGELOG.md`).

| Area | State |
|------|-------|
| Data mirror | `data/ILIARIRates.csv`, `data/SARIRates.csv`, `data/sentinelTestsDetectionsPositivity.csv`, `data/SARITestsDetectionsPositivity.csv`, `data/metadata.json` |
| Coverage | ILI/ARI from 2014-W40 (total age only before 2022-W25), SARI and positivity (primary care, hospital) from 2022-W25 |
| Daily sync | `.github/workflows/sync-ecdc-data.yml` + `scripts/sync_ecdc.py`, 18:17 UTC |
| Library | `get_ili/get_ari/get_sari/get_data`, `get_positivity`, `coverage`, `list_countries`, `list_seasons`, `latest_week`, cache with hourly ETag checks |
| CI | `.github/workflows/ci.yml`: ruff, mypy, pytest on Python 3.10–3.12, strict docs build |
| Docs | https://pyerviss.readthedocs.io (Sphinx, `docs/`), rebuilt on every push to `main` |
| Releases | `.github/workflows/publish.yml`: a GitHub release `vX.Y.Z` publishes to PyPI (trusted publishing) |

## Next

### Documentation on Read the Docs
- [x] Tool: Sphinx + MyST (Markdown pages) + Furo theme; API reference from the
      Google-style docstrings (autodoc + napoleon)
- [x] Pages: installation and quickstart; querying (countries, weeks, seasons, age groups);
      output format; **units** (per-country table, Slovakia ICU note,
      comparability caveat); data sources, sync and history (ECDC, RespiCast import,
      retained rows); caching and offline use; API reference generated from docstrings;
      disclaimer
- [x] `.readthedocs.yaml` and a `docs` optional dependency group
- [x] Build the docs in CI (fail on warnings) so they can't silently break
- [x] Docs link and badges in the README; `Documentation` URL in `pyproject.toml`
- [x] Import the project on readthedocs.org
- [ ] Release 0.1.1 so the PyPI page shows the Documentation link

### Maintenance
- [ ] **Confirm the daily sync works on GitHub.** It has never run: the first scheduled
      slot (2026-10-02 18:17 UTC) produced no run. Trigger it once manually (Actions →
      Sync ECDC data → Run workflow); if scheduled runs still don't appear, investigate.
      The first run that finds new ECDC data is also the first test of the bot
      committing to `main`
- [x] Single-source the version: `pyproject.toml` only; `__version__` is read from the
      installed package metadata
- [x] Add a `CHANGELOG.md` (Keep a Changelog); use it for release notes
- [ ] Test on Python 3.13 in CI and add the classifier
- [ ] Delete merged branches on GitHub

### Later
- [ ] Influenza subtypes (A(H1)pdm09, A(H3), B/Victoria...) and RSV-A/B: detections are
      already mirrored in the virology files; derived subtype positivity is
      `subtype detections / influenza tests × 100`, understated by unsubtyped detections
- [ ] Other ERVISS datasets: non-sentinel severity (hospital/ICU admissions, deaths),
      non-sentinel tests and detections. Variants and sequencing are partly sourced from
      GISAID, whose terms restrict redistribution: check before mirroring
- [ ] Minimal plotting layer (discussed, on hold): `add_season_week()` (season and
      week-of-season columns) and a matplotlib `plot_seasons()` season overlay as an
      optional `pyerviss[plot]` extra, labelling axes from `unit` and refusing mixed
      units on one axis
- [ ] Snapshots (deferred): ECDC publishes dated snapshots since 2023-11-24, useful for
      reproducing what was known at a given date (e.g. forecast evaluation)

## Decisions

Recorded here so they aren't re-litigated.

- **Mirror, don't proxy:** the package downloads from this repo, not ECDC. The repo keeps
  rows ECDC later removes (cumulative merge keyed on country, week, indicator, age; ECDC
  values win on overlap).
- **Storage:** CSV in ECDC's column layout, deterministic sort and number formatting so
  git diffs show real revisions only. No data ships in the pip package.
- **Units:** a `unit` column states what each value measures. Rates are per 100,000. ECDC's per-100 series are
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
  year_week, date, age, value, unit`; positivity adds `setting`, `pathogen`, `tests`,
  `detections`. ISO2 country codes, plus `EU` for ECDC's EU/EEA aggregate. `indicator` makes
  combined results (`pd.concat`) safe.
- **Releases:** record changes under "Unreleased" in `CHANGELOG.md` as they are merged.
  To release: rename "Unreleased" to the version and date, bump `version` in
  `pyproject.toml` (the only place the version is written), merge, and publish a GitHub release tagged `vX.Y.Z` with that
  section as its notes. Versions can never be re-uploaded to PyPI.
