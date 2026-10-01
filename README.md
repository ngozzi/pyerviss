# pyerviss

[![CI](https://github.com/ngozzi/pyerviss/actions/workflows/ci.yml/badge.svg)](https://github.com/ngozzi/pyerviss/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pyerviss)](https://pypi.org/project/pyerviss/)
[![Docs](https://readthedocs.org/projects/pyerviss/badge/?version=latest)](https://pyerviss.readthedocs.io)

Unofficial Python API to ERVISS, the European Respiratory Virus Surveillance Summary

Weekly ILI, ARI and SARI rates for EU/EEA countries as pandas DataFrames, from ECDC's
[ERVISS](https://erviss.org) data, with ILI and ARI history back to 2014.

> **Disclaimer:** pyerviss is an independent, unofficial project. It is not affiliated
> with, endorsed by, or maintained by the European Centre for Disease Prevention and
> Control (ECDC) or ERVISS. The data is mirrored from ECDC's public repository and
> processed here (units are harmonized, history is added from other sources, and rows
> ECDC later removes are kept), so it can differ from the official figures. For official
> data, see [erviss.org](https://erviss.org).

Documentation: **https://pyerviss.readthedocs.io**

## Installation

```bash
pip install pyerviss
```

Requires Python 3.10+.

## Usage

```python
import pyerviss as pv

# ILI rates for Italy and Malta (names or ISO2 codes) in the 2024/25 season
df = pv.get_ili(countries=["Italy", "MT"], season="2024/25", age_groups="total")

# SARI rates for people aged 65+ between two dates (weeks or dates, inclusive)
df = pv.get_sari(start="2024-10-01", end="2025-03-31", age_groups="65+")

# ARI rates for all countries
df = pv.get_ari()
```

Every query returns one row per country, week and age group:

| country | country_code | year_week | date | age | value | denominator |
|---|---|---|---|---|---|---|
| Italy | IT | 2024-W42 | 2024-10-20 | total | 592.8 | population |
| Malta | MT | 2024-W42 | 2024-10-20 | total | 5800.0 | consultations |

- `date` is the last day (Sunday) of the ISO week.
- A season such as `"2024/25"` runs from 2024-W40 to 2025-W39.
- `value` is a rate per 100,000 of `denominator`: `population`, `consultations` or
  `admissions` (see [Units](https://github.com/ngozzi/pyerviss#units)).
- Data before 2022-W25 is only available for the `"total"` age group.

Finding out what is available:

```python
pv.coverage("ili")         # per country: first/last week, number of weeks, age groups
pv.list_countries("sari")  # countries with SARI data
pv.list_seasons()          # ["2014/15", ..., "2025/26"]
pv.latest_week()           # most recent week with data, e.g. "2026-W38"
```

Data is downloaded on first use and cached locally (`~/.cache/pyerviss` on Linux),
then checked for updates at most once an hour. Without a connection, the cached copy is
used. `pv.update_data()` checks for updates now and `pv.clear_cache()` removes the cache.

## Data

`data/` mirrors ILI, ARI and SARI rates from ECDC's
[Respiratory_viruses_weekly_data](https://github.com/EU-ECDC/Respiratory_viruses_weekly_data),
synced daily and merged cumulatively (rows ECDC removes are kept).
ILI and ARI (total age group) also go back to 2014-W40, imported once from the
[RespiCast](https://github.com/european-modelling-hubs/RespiCast-SyndromicIndicators)
ERVISS snapshots of 2024-10-11 for weeks ECDC no longer publishes.

### Units

Every `value` is a rate per 100,000 of the row's `denominator`, which differs by country:

| Indicator | Countries | `denominator` | Unit |
|---|---|---|---|
| ILI, ARI | most | `population` | per 100,000 population |
| ILI, ARI | Finland | `consultations` | per 100,000 consultations |
| ILI, ARI | Cyprus, Luxembourg, Malta | `consultations` | per 100,000 consultations (ECDC: per 100 consultations; multiplied by 1000) |
| SARI | most | `population` | per 100,000 hospital catchment population |
| SARI | Greece, Ireland, Latvia, Luxembourg | `admissions` | per 100,000 hospital admissions (ECDC: per 100 total hospital admissions; multiplied by 1000) |

Rates with different denominators are not directly comparable. Slovakia's SARI data is based
on ICU admissions only. The sync fails if a country's values change scale by orders of
magnitude, which would indicate a unit change upstream.

## Credits

Data from the European Centre for Disease Prevention and Control (ECDC), [European
Respiratory Virus Surveillance Summary (ERVISS)](https://erviss.org), published in
[EU-ECDC/Respiratory_viruses_weekly_data](https://github.com/EU-ECDC/Respiratory_viruses_weekly_data);
see that repository for the data's terms of use. Historical ILI and ARI data via the
[European RespiCast Hub](https://github.com/european-modelling-hubs/RespiCast-SyndromicIndicators).

## License

The code is released under the [MIT License](https://github.com/ngozzi/pyerviss/blob/main/LICENSE).
