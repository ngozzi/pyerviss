# PyERVISS Implementation Plan

Python package providing an API for ERVISS (European Respiratory Virus Surveillance Summary) data, focusing initially on ILI, ARI, and SARI indicators.

## Overview

| Aspect | Decision |
|--------|----------|
| **Distribution** | Pip package with remote data fetching (data downloaded from GitHub on first use, cached locally) |
| **Minimum Python** | 3.10+ |
| **Data Source** | [EU-ECDC/Respiratory_viruses_weekly_data](https://github.com/EU-ECDC/Respiratory_viruses_weekly_data) |

## Data Context

### Source Files

| File | Contents | Countries |
|------|----------|-----------|
| `ILIARIRates.csv` | ILI + ARI consultation rates | 29 |
| `SARIRates.csv` | SARI hospitalization rates | 15 |

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

- Available from **2023-11-24** onwards
- Updated weekly on Fridays
- Naming format: `YYYY-MM-DD_[DataType].csv`
- Location: `data/snapshots/` in ECDC repo

---

## Project Structure

```
pyerviss/
├── .github/workflows/
│   └── ci.yml                 # Tests, linting, type checking
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
└── TODO.md                    # This file
```

**Local cache location**: `~/.cache/pyerviss/` (via platformdirs)

---

## Implementation Checklist

### Phase 1: Project Setup

- [ ] **Create `pyproject.toml`**
  - Build system: hatchling
  - Dependencies: `pandas>=2.0.0`, `requests>=2.28.0`, `platformdirs>=3.0.0`
  - Dev deps: pytest, ruff, mypy, responses (for mocking HTTP)
  - Minimum Python: 3.10

- [ ] **Create package structure**
  - `src/pyerviss/__init__.py` with version and public API exports
  - `src/pyerviss/exceptions.py` for custom errors

- [ ] **Remove `raw-data/` folder** (no longer needed, data fetched remotely)

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
  ECDC_RAW_URL = "https://raw.githubusercontent.com/EU-ECDC/Respiratory_viruses_weekly_data/main/data/"

  def fetch_ili_ari_data(force_refresh: bool = False) -> pd.DataFrame

  def fetch_sari_data(force_refresh: bool = False) -> pd.DataFrame

  def fetch_snapshot(snapshot_date: date, data_type: str) -> pd.DataFrame

  def list_available_snapshots() -> list[date]
      # Uses GitHub API to list snapshot files

  def update_data() -> None
      # Force refresh all cached data
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

- [ ] **`.github/workflows/ci.yml`**
  - Matrix: Python 3.10, 3.11, 3.12
  - Steps: lint (ruff), type check (mypy), test (pytest)

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

4. **Update `data_loader.py`** to fetch the new file

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

   # First call fetches data from GitHub
   df = pv.get_ili(countries="Germany", season="2024/25")
   print(df.head())
   print(f"Shape: {df.shape}")

   # Check available data
   print(pv.list_countries("ili"))
   print(pv.list_seasons())
   print(pv.get_latest_week())

   # Force refresh
   pv.update_data()
   ```

4. **Verify cache**:
   ```bash
   ls -la ~/.cache/pyerviss/
   ```

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
