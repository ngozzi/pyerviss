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

- [ ] **`src/pyerviss/utils.py`**
  ```python
  def yearweek_to_date(yearweek: str) -> date
      # "2025-W03" → date (Monday of that week)

  def date_to_yearweek(d: date) -> str
      # date → "2025-W03"

  def parse_season(season: str) -> tuple[str, str]
      # "2024/25" → ("2024-W40", "2025-W20")
  ```

- [ ] **`src/pyerviss/types.py`**
  - Type aliases: `Country`, `AgeGroup`, `Season`
  - Constants: `COUNTRIES_ILI_ARI`, `COUNTRIES_SARI`, `AGE_GROUPS`

- [ ] **`src/pyerviss/cache.py`**
  ```python
  def get_cache_dir() -> Path
      # Returns ~/.cache/pyerviss/ via platformdirs

  def is_cache_stale(file_path: Path, max_age_hours: int = 24) -> bool

  def clear_cache() -> None
  ```

- [ ] **`src/pyerviss/data_loader.py`**
  ```python
  # Fetch from THIS repository, not ECDC
  REPO_RAW_URL = "https://raw.githubusercontent.com/ngozzi/pyerviss/main/data/"

  # Alternative: use github.com API to get latest commit data
  REPO_API_URL = "https://api.github.com/repos/ngozzi/pyerviss/contents/data"

  def fetch_ili_ari_data(force_refresh: bool = False) -> pd.DataFrame
      # Fetches from this repo's data/ILIARIRates.csv

  def fetch_sari_data(force_refresh: bool = False) -> pd.DataFrame
      # Fetches from this repo's data/SARIRates.csv

  def fetch_snapshot(snapshot_date: date, data_type: str) -> pd.DataFrame
      # Fetches from this repo's data/snapshots/YYYY-MM-DD_[type].csv
      # Note: Snapshots are cumulative (include all historical data up to that date)

  def list_available_snapshots() -> list[date]
      # Lists snapshot files from this repo's data/snapshots/
      # Returns dates when data was updated (not necessarily weekly if no changes)

  def get_metadata() -> dict
      # Fetches data/metadata.json to check last update time

  def update_data() -> None
      # Force refresh all cached data from this repo
  ```

### Phase 3: Indicator Pattern (Extensibility)

- [ ] **`src/pyerviss/indicators/base.py`**
  ```python
  class BaseIndicator(ABC):
      @property
      @abstractmethod
      def name(self) -> str: ...

      @property
      @abstractmethod
      def data_file(self) -> str: ...

      @property
      @abstractmethod
      def indicator_column_value(self) -> str: ...

      def query(
          self,
          countries: list[str] | None = None,
          start_date: date | None = None,
          end_date: date | None = None,
          age_groups: list[str] | None = None,
      ) -> pd.DataFrame: ...
  ```

- [ ] **Concrete indicators**
  - `ili.py`: `ILIIndicator` (data_file="ILIARIRates.csv", indicator="ILIconsultationrate")
  - `ari.py`: `ARIIndicator` (data_file="ILIARIRates.csv", indicator="ARIconsultationrate")
  - `sari.py`: `SARIIndicator` (data_file="SARIRates.csv", indicator="SARIrate")

- [ ] **`src/pyerviss/indicators/__init__.py`**
  ```python
  INDICATORS = {
      "ili": ILIIndicator(),
      "ari": ARIIndicator(),
      "sari": SARIIndicator(),
  }

  def get_indicator(name: str) -> BaseIndicator: ...
  ```

### Phase 4: Public API

- [ ] **`src/pyerviss/api.py`**
  ```python
  def get_ili(
      countries: str | list[str] | None = None,
      start_date: date | str | None = None,
      end_date: date | str | None = None,
      season: str | list[str] | None = None,  # Mutually exclusive with dates
      age_groups: str | list[str] | None = None,
  ) -> pd.DataFrame

  def get_ari(...) -> pd.DataFrame

  def get_sari(...) -> pd.DataFrame

  def list_countries(indicator: str = "ili") -> list[str]

  def list_seasons() -> list[str]

  def get_latest_week() -> str

  # Snapshot access
  def get_ili_snapshot(snapshot_date: date | str, **filters) -> pd.DataFrame
  def get_ari_snapshot(snapshot_date: date | str, **filters) -> pd.DataFrame
  def get_sari_snapshot(snapshot_date: date | str, **filters) -> pd.DataFrame

  def list_snapshots() -> list[date]

  # Cache management
  def update_data() -> None
  def clear_cache() -> None
  ```

- [ ] **`src/pyerviss/__init__.py`** - Export public API
  ```python
  from .api import (
      get_ili, get_ari, get_sari,
      get_ili_snapshot, get_ari_snapshot, get_sari_snapshot,
      list_countries, list_seasons, list_snapshots,
      get_latest_week, update_data, clear_cache,
  )

  __version__ = "0.1.0"
  ```

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

# Basic query - all ILI data for Germany
df = pv.get_ili(countries="Germany")

# Multiple countries + season filter
df = pv.get_ili(countries=["France", "Spain", "Italy"], season="2024/25")

# Date range + age group filter
df = pv.get_sari(
    start_date="2024-10-01",
    end_date="2025-03-31",
    age_groups="65+"
)

# Multiple age groups
df = pv.get_ili(countries="Austria", age_groups=["0-4", "5-14"])

# Utility functions
pv.list_countries("sari")   # ["Austria", "Belgium", ...]
pv.list_countries("ili")    # More countries than SARI
pv.list_seasons()           # ["2021/22", "2022/23", "2023/24", "2024/25"]
pv.get_latest_week()        # "2026-W03"

# Historical snapshot access
df = pv.get_ili_snapshot("2024-06-01", countries="Austria")
pv.list_snapshots()         # [date(2023, 11, 24), date(2023, 12, 1), ...]

# Cache management
pv.update_data()            # Force refresh all cached data
pv.clear_cache()            # Remove all cached files
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
