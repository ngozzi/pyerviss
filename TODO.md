# PyERVISS Implementation Plan

Python package providing an API for ERVISS (European Respiratory Virus Surveillance Summary) data, focusing initially on ILI, ARI, and SARI indicators.

## Overview

| Aspect | Decision |
|--------|----------|
| **Distribution** | Lightweight pip package (no data files included) |
| **Minimum Python** | 3.10+ |
| **Data Source** | This repository (mirrored from ECDC via GitHub Actions) |
| **Data Update** | Automated weekly sync from [EU-ECDC/Respiratory_viruses_weekly_data](https://github.com/EU-ECDC/Respiratory_viruses_weekly_data) |
| **Data Fetching** | API fetches from this repo's GitHub (not ECDC directly) |

## Data Context

### Source Files

| File | Contents | Countries |
|------|----------|-----------|
| `ILIARIRates.csv` | ILI + ARI consultation rates | 28 |
| `SARIRates.csv` | SARI hospitalization rates | 16 |

### Data Structure

All files share the same column structure:

| Column | Description | Example Values |
|--------|-------------|----------------|
| `survtype` | Surveillance type | "primary care syndromic", "SARI syndromic" |
| `countryname` | Country name | "Austria", "Germany", "France" |
| `yearweek` | ISO week format | "2025-W03", "2024-W52" |
| `indicator` | Rate type | "ILIconsultationrate", "ARIconsultationrate", "SARIrate" |
| `age` | Age group | "0-4", "5-14", "15-64", "65+", "total" |
| `value` | Numeric rate | 4345.3 |

### Historical Snapshots

> **Deferred.** For now we only keep the latest cumulative files; snapshot support is on hold.


- Available from **2023-11-24** onwards
- Updated weekly on Fridays
- Naming format: `YYYY-MM-DD_[DataType].csv`
- Location: `data/snapshots/` in this repo (synced from ECDC)

### Data Mirror Strategy

**Why we mirror data:**
- ECDC has removed historical data that we want to preserve
- Ensures API stability and data persistence
- Maintains complete historical archive beyond what ECDC provides

**Cumulative merge strategy:**
1. **Initial seed**: Historical data (pre-2023) provided manually
2. **Weekly sync**: Fetch latest from ECDC and merge intelligently
3. **Merge logic**:
   - Keep ALL historical records (never delete data)
   - UPDATE existing records if ECDC has newer values (based on yearweek+country+indicator+age)
   - ADD new records from ECDC
4. **Result**: Continuously growing dataset that preserves history

**Sync mechanism:**
- GitHub Actions workflow runs **daily** (ECDC update timing varies; commits only on change)
- Fetches latest data from ECDC repo
- Merges with existing data (preserving historical records)
- Saves merged result as the current files (snapshots deferred)
- Updates metadata.json with record counts and date ranges
- **Commits only if data actually changed** (prevents empty commits from multiple runs)

---

## Project Structure

```
pyerviss/
├── .github/workflows/
│   ├── ci.yml                 # Tests, linting, type checking
│   └── sync-ecdc-data.yml     # Weekly data sync from ECDC
├── data/                      # Data mirror (NOT in pip package)
│   ├── ILIARIRates.csv        # Cumulative dataset (all historical + ECDC updates)
│   ├── SARIRates.csv          # Cumulative dataset (all historical + ECDC updates)
│   ├── snapshots/             # Weekly cumulative snapshots
│   │   ├── 2026-01-26_ILIARIRates.csv  # Initial seed (your historical data)
│   │   ├── 2026-01-26_SARIRates.csv    # Initial seed (your historical data)
│   │   ├── 2026-01-31_ILIARIRates.csv  # After first sync (merged)
│   │   ├── 2026-01-31_SARIRates.csv    # After first sync (merged)
│   │   └── ...
│   └── metadata.json          # Last update, record counts, date ranges
├── src/pyerviss/
│   ├── __init__.py            # Public exports
│   ├── api.py                 # get_ili(), get_ari(), get_sari()
│   ├── data_loader.py         # Fetch from GitHub + local cache
│   ├── cache.py               # Cache management (location, refresh)
│   ├── utils.py               # yearweek_to_date, parse_season
│   ├── types.py               # Type aliases, constants
│   ├── exceptions.py          # Custom exceptions
│   └── indicators/            # Extensible indicator pattern
│       ├── __init__.py        # Indicator registry
│       ├── base.py            # BaseIndicator ABC
│       ├── ili.py             # ILI indicator
│       ├── ari.py             # ARI indicator
│       └── sari.py            # SARI indicator
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Pytest fixtures
│   ├── test_api.py
│   ├── test_utils.py
│   ├── test_data_loader.py
│   └── fixtures/
│       ├── sample_ili_ari.csv
│       └── sample_sari.csv
├── pyproject.toml
├── README.md
├── .gitignore                 # Excludes local cache, but includes data/
└── TODO.md                    # This file
```

**Notes:**
- `data/` folder **is tracked in git** (contains mirrored ECDC data)
- Pip package **does not include** `data/` folder
- Local cache location: `~/.cache/pyerviss/` (via platformdirs) for user-side data caching

---

## Implementation Checklist

### Phase 1: Project Setup

- [x] **Create `pyproject.toml`**
  - Build system: hatchling
  - **IMPORTANT**: Exclude `data/` folder from package distribution
  - Dependencies: `pandas>=2.0.0`, `requests>=2.28.0`, `platformdirs>=3.0.0`
  - Dev deps: pytest, ruff, mypy, responses (for mocking HTTP)
  - Minimum Python: 3.10

- [x] **Create package structure**
  - `src/pyerviss/__init__.py` with version and public API exports
  - `src/pyerviss/exceptions.py` for custom errors

- [ ] **Create `data/` folder structure and seed with historical data**
  - [x] Seeded from current ECDC data (2022-W25 onwards) via `scripts/sync_ecdc.py`
  - [x] Merged ILI/ARI total-age history from 2014-W40 (RespiCast 2024-10-11 snapshots) via `scripts/import_respicast.py`
  - `data/ILIARIRates.csv` (your complete historical dataset)
  - `data/SARIRates.csv` (your complete historical dataset)
  - `data/snapshots/` directory
  - `data/snapshots/YYYY-MM-DD_ILIARIRates.csv` (copy of initial historical data)
  - `data/snapshots/YYYY-MM-DD_SARIRates.csv` (copy of initial historical data)
  - `data/metadata.json` with schema:
    ```json
    {
      "last_update": "YYYY-MM-DD",
      "ecdc_commit": "sha_or_null",
      "records_count": {
        "ILIARIRates": 125000,
        "SARIRates": 45000
      },
      "date_range": {
        "ILIARIRates": {"start": "2015-W01", "end": "2026-W03"},
        "SARIRates": {"start": "2017-W20", "end": "2026-W03"}
      },
      "data_sources": [
        "Historical data seeded YYYY-MM-DD",
        "Weekly ECDC sync (cumulative merge)"
      ]
    }
    ```

- [x] **Create `.gitignore`**
  - Include standard Python ignores
  - **DO NOT ignore `data/`** - it must be tracked
  - Ignore local cache: `__pycache__/`, `.pytest_cache/`, etc.

- [x] **Create `.github/workflows/sync-ecdc-data.yml`** (logic in `scripts/sync_ecdc.py`)
  - **Schedule**: daily at 18:17 UTC (`17 18 * * *`); ECDC's update day and time vary
  - Manual trigger: `workflow_dispatch`
  - **Smart update logic**: Only commit if data actually changed (prevents empty commits)
  - Steps:
    1. Fetch latest data from ECDC repo (ILIARIRates.csv, SARIRates.csv)
    2. Load current cumulative data from this repo
    3. **Merge strategy** (using pandas):
       ```python
       # Merge key: countryname + yearweek + indicator + age
       merged = pd.concat([our_data, ecdc_data]).drop_duplicates(
           subset=['countryname', 'yearweek', 'indicator', 'age'],
           keep='last'  # ECDC values overwrite if duplicate
       ).sort_values(['yearweek', 'countryname', 'indicator', 'age'])
       ```
    4. Compare merged data with current data (hash comparison or record count)
    5. **Only if data changed**:
       - Save merged data as `data/ILIARIRates.csv` and `data/SARIRates.csv`
       - Update `metadata.json` (counts, date ranges, last update)
       - Commit and push changes with message: "Data sync: YYYY-MM-DD - [N new records, M updated]"
    6. **If no changes**: Exit without committing (prevents noise from multiple weekly runs)

### Phase 2: Core Utilities

- [x] **`src/pyerviss/utils.py`**: ISO week and season helpers
  - `yearweek_to_date("2024-W40")` → `date(2024, 10, 6)` (**Sunday**, week end; matches RespiCast `truth_date`)
  - `date_to_yearweek`, `to_yearweek` (accepts "2024-W40", "2024-10-01", `date`, `datetime`)
  - `parse_season("2024/25")` → `("2024-W40", "2025-W39")` (**full year**, W40 to W39)
  - `season_of("2025-W01")` → `"2024/25"`

- [x] **`src/pyerviss/types.py`**: hardcoded country lists replaced by lists derived from the data; ISO2 codes

- [x] **`src/pyerviss/cache.py`**: `get_cache_dir()` (platformdirs; `PYERVISS_CACHE_DIR` override), `clear_cache()`

- [x] **`src/pyerviss/data_loader.py`**
  - Downloads from `https://raw.githubusercontent.com/ngozzi/pyerviss/main/data/` (`PYERVISS_DATA_URL` override); **requires the repo to be public**
  - Checks each file for updates at most once per hour via ETag (unchanged files are not re-downloaded)
  - Offline with a cached copy: warns and uses the cache; atomic writes; parsed files kept in memory
  - `fetch_file()`, `load_csv()`, `get_metadata()`, `update_data()`

### Phase 3: Indicator Pattern (Extensibility)

- [x] **`src/pyerviss/indicators/`**: `Indicator` dataclass (`base.py`) and the `INDICATORS`
  registry with `get_indicator()` (`__init__.py`); a new indicator is one registry entry

### Phase 4: Public API

- [x] **`src/pyerviss/api.py`**
  ```python
  def get_data(
      indicator: str,  # "ili", "ari", "sari"
      countries: str | list[str] | None = None,  # names or ISO2 codes, case-insensitive
      start: str | date | None = None,  # "2024-W40", "2024-10-01" or date; inclusive
      end: str | date | None = None,  # inclusive
      season: str | list[str] | None = None,  # "2024/25" = 2024-W40..2025-W39; not with start/end
      age_groups: str | list[str] | None = None,  # default: all
  ) -> pd.DataFrame

  def get_ili(...) -> pd.DataFrame  # get_data("ili", ...)
  def get_ari(...) -> pd.DataFrame
  def get_sari(...) -> pd.DataFrame

  def coverage(indicator: str) -> pd.DataFrame  # per country: first/last week, n weeks
  def list_countries(indicator: str) -> list[str]
  def list_seasons() -> list[str]
  def latest_week(indicator: str | None = None) -> str

  def update_data() -> None
  def clear_cache() -> None
  ```
  - Output: long format, one row per country/week/age, sorted by country, date, age:
    `country, country_code, year_week, date, age, value, denominator`
    - `date`: Sunday ending the ISO week
    - `denominator`: "population" or "consultations" (CY, FI, LU, MT); all values per 100,000
  - Countries validated against the data: "did you mean" suggestions for typos, clear
    error when a country has no data for the indicator
  - Snapshot functions deferred with snapshots

- [x] **`src/pyerviss/__init__.py`**: export the public API

### Phase 5: Testing

- [ ] **Test fixtures** (`tests/fixtures/`)
  - `sample_ili_ari.csv`: Small subset with known values
  - `sample_sari.csv`: Small subset with known values

- [ ] **Test cases** (`tests/test_*.py`)
  - API returns DataFrame
  - Filtering by country (single and multiple)
  - Filtering by date range
  - Filtering by season
  - Filtering by age group
  - Season and dates are mutually exclusive (raises error)
  - SARI has fewer countries than ILI/ARI
  - Snapshot loading
  - Cache behavior (use `responses` library to mock HTTP)

- [x] **`.github/workflows/ci.yml`**
  - Matrix: Python 3.10, 3.11, 3.12
  - Steps: lint (ruff), type check (mypy), test (pytest)

- [ ] **Test data sync workflow**
  - Manually trigger `.github/workflows/sync-ecdc-data.yml`
  - Verify data files are updated in `data/` (should be cumulative merge)
  - Verify no historical records were lost
  - Verify new ECDC records were added
  - Verify existing records were updated if ECDC had changes
  - Verify metadata.json is updated with correct counts and date ranges
  - Verify git commit is created only if data changed
  - Verify snapshot is created in `data/snapshots/YYYY-MM-DD_*.csv`

---

## API Usage Examples

```python
import pyerviss as pv

# All ILI data for Germany
df = pv.get_ili(countries="Germany")

# Names or ISO2 codes + season (2024-W40 to 2025-W39)
df = pv.get_ili(countries=["FR", "Spain", "IT"], season="2024/25")

# Date range + age group
df = pv.get_sari(start="2024-10-01", end="2025-03-31", age_groups="65+")

# Discovery
pv.coverage("ili")  # first/last week and n weeks per country
pv.list_countries("sari")
pv.list_seasons()  # ["2014/15", ..., "2026/27"]
pv.latest_week()  # "2026-W38"

# Cache management
pv.update_data()  # check for new data now
pv.clear_cache()  # remove cached files
```

---

## Future Extensibility

The indicator pattern makes it easy to add new data types. To add flu subtypes:

1. **Create indicator class** (`src/pyerviss/indicators/flu_subtype.py`):
   ```python
   class FluSubtypeIndicator(BaseIndicator):
       @property
       def name(self) -> str:
           return "flu_subtype"

       @property
       def data_file(self) -> str:
           return "activityFluTypeSubtype.csv"

       @property
       def indicator_column_value(self) -> str:
           return "detections"
   ```

2. **Register in `indicators/__init__.py`**:
   ```python
   INDICATORS["flu_subtype"] = FluSubtypeIndicator()
   ```

3. **Add public API function** (`api.py`):
   ```python
   def get_flu_subtype(...) -> pd.DataFrame: ...
   ```

4. **Update `data_loader.py`** to fetch the new file from this repo

5. **Update GitHub Actions workflow** to sync the new file from ECDC

---

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Historical Data (Manual Seed)                               │
│ - Pre-2023 data that ECDC removed                           │
│ - Provided as initial ILIARIRates.csv and SARIRates.csv    │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ Initial commit to pyerviss repo
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ pyerviss Repository (Cumulative Dataset)                    │
│ - data/ILIARIRates.csv      (cumulative)                    │
│ - data/SARIRates.csv        (cumulative)                    │
│ - data/snapshots/*.csv      (dated cumulative snapshots)    │
│ - data/metadata.json                                        │
└────────────────┬────────────────────────────────────────────┘
                 ▲
                 │ Weekly cumulative merge
                 │ .github/workflows/sync-ecdc-data.yml
                 │
┌────────────────┴────────────────────────────────────────────┐
│ EU-ECDC/Respiratory_viruses_weekly_data (Source)            │
│ - Updated every Friday                                      │
│ - Official ECDC data (limited historical)                   │
└─────────────────────────────────────────────────────────────┘

                 ┌────────────────────────────────────────────┐
                 │ pyerviss Repository (Cumulative Dataset)   │
                 │ - Complete historical archive              │
                 │ - Weekly ECDC updates merged in            │
                 └────────────────┬───────────────────────────┘
                                  │
                                  │ HTTP fetch (via requests)
                                  │ https://raw.githubusercontent.com/...
                                  ▼
                 ┌────────────────────────────────────────────┐
                 │ pyerviss pip package (User's machine)      │
                 │ - Fetches data from pyerviss repo          │
                 │ - Caches locally in ~/.cache/pyerviss/     │
                 │ - Provides API: get_ili(), get_ari()...    │
                 └────────────────────────────────────────────┘
```

**Merge Strategy Details:**
- **Never delete**: Historical records are preserved even if ECDC removes them
- **Update on match**: If ECDC has same (yearweek, country, indicator, age), use ECDC's value
- **Add new**: New records from ECDC are appended
- **Result**: Growing dataset with complete history

**Benefits:**
- Data independence from ECDC changes
- Complete historical archive beyond what ECDC provides
- Protection against ECDC data removal
- Faster API responses (no ECDC dependency)
- Lightweight pip package (no bundled data)
- Audit trail via dated snapshots

---

## Verification

After implementation, verify with:

1. **Run tests**:
   ```bash
   pytest tests/ -v
   ```

2. **Type check**:
   ```bash
   mypy src/
   ```

3. **Manual API test**:
   ```python
   import pyerviss as pv

   # First call fetches data from this repo's GitHub
   df = pv.get_ili(countries="Germany", season="2024/25")
   print(df.head())
   print(f"Shape: {df.shape}")

   # Check available data
   print(pv.list_countries("ili"))
   print(pv.list_seasons())
   print(pv.get_latest_week())

   # Check metadata
   from pyerviss.data_loader import get_metadata
   print(get_metadata())  # Should show last update time

   # Force refresh
   pv.update_data()
   ```

4. **Verify cache**:
   ```bash
   ls -la ~/.cache/pyerviss/
   ```

5. **Verify data sync and merge behavior**:
   - Check that `data/` folder has latest files
   - Verify GitHub Actions workflow ran successfully
   - **Verify historical data preservation**:
     ```python
     import pandas as pd

     # Load initial and current data
     initial = pd.read_csv('data/snapshots/2026-01-26_ILIARIRates.csv')
     current = pd.read_csv('data/ILIARIRates.csv')

     # Check that all initial records still exist
     initial_keys = initial[['countryname', 'yearweek', 'indicator', 'age']].drop_duplicates()
     current_keys = current[['countryname', 'yearweek', 'indicator', 'age']].drop_duplicates()

     # This should be empty (no lost records)
     lost_records = set(map(tuple, initial_keys.values)) - set(map(tuple, current_keys.values))
     print(f"Lost records: {len(lost_records)}")  # Should be 0

     # Check growth
     print(f"Initial records: {len(initial)}")
     print(f"Current records: {len(current)}")  # Should be >= initial
     ```
   - Verify metadata.json reflects correct counts and date ranges

---

## Dependencies

### Runtime
| Package | Version | Purpose |
|---------|---------|---------|
| pandas | >=2.0.0 | DataFrame operations |
| requests | >=2.28.0 | HTTP requests to GitHub |
| platformdirs | >=3.0.0 | Cross-platform cache directory |

### Development
| Package | Purpose |
|---------|---------|
| pytest | Testing framework |
| pytest-cov | Coverage reporting |
| ruff | Linting and formatting |
| mypy | Type checking |
| pandas-stubs | Type hints for pandas |
| responses | Mock HTTP responses in tests |
