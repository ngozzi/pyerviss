# Querying data

Three functions return data, one per indicator. They take the same filters, all optional:

```python
import pyerviss as pv

pv.get_ili(countries=None, start=None, end=None, season=None, age_groups=None)
pv.get_ari(...)
pv.get_sari(...)
```

| Function | Indicator | Setting |
|---|---|---|
| {func}`~pyerviss.get_ili` | Influenza-like illness consultation rate | Primary care |
| {func}`~pyerviss.get_ari` | Acute respiratory infection consultation rate | Primary care |
| {func}`~pyerviss.get_sari` | Severe acute respiratory infection rate | Hospitals |

With no filters, a function returns everything available for its indicator.
{func}`~pyerviss.get_data` does the same with the indicator as its first argument
(`"ili"`, `"ari"` or `"sari"`), which is convenient in loops.

## Output format

Every query returns a long-format DataFrame: one row per country, week and age group,
sorted by country, date and age group.

```python
pv.get_sari(countries="Spain", start="2025-01-01", end="2025-01-31")
```

```text
  country country_code year_week       date    age  value denominator
0   Spain           ES  2025-W01 2025-01-05    0-4   57.2  population
1   Spain           ES  2025-W01 2025-01-05   5-14    3.8  population
2   Spain           ES  2025-W01 2025-01-05  15-64    6.3  population
3   Spain           ES  2025-W01 2025-01-05    65+   81.3  population
4   Spain           ES  2025-W01 2025-01-05  total   22.9  population
5   Spain           ES  2025-W02 2025-01-12    0-4   42.8  population
...
```

| Column | Description |
|---|---|
| `country` | Country name as used by ECDC, e.g. `"Czechia"` |
| `country_code` | ISO 3166-1 alpha-2 code, e.g. `"CZ"` (Greece is `"GR"`) |
| `year_week` | ISO 8601 week, e.g. `"2025-W01"` |
| `date` | Last day (Sunday) of the ISO week, as a pandas datetime |
| `age` | `"0-4"`, `"5-14"`, `"15-64"`, `"65+"` or `"total"` |
| `value` | Rate per 100,000 of the denominator |
| `denominator` | `"population"`, `"consultations"` or `"admissions"`; see {doc}`units` |

A query that matches nothing returns an empty DataFrame with the same columns.

For one column per country, pivot the result:

```python
df = pv.get_ili(countries=["Belgium", "Netherlands"], season="2024/25", age_groups="total")
df.pivot(index="date", columns="country", values="value")
```

```text
country     Belgium  Netherlands
date
2024-10-06    225.8         18.8
2024-10-13    226.4         19.8
2024-10-20    185.6         15.8
2024-10-27    120.7          9.6
...
```

:::{warning}
Rates are not always comparable across countries: case definitions, surveillance systems
and denominators differ. See {doc}`units`.
:::

## Countries

Pass a country name or ISO2 code, or a list mixing both. Matching is case-insensitive.

```python
pv.get_ili(countries="Italy")
pv.get_ili(countries=["FR", "spain", "IT"])
```

`"EL"` (the EU code for Greece) and `"Czech Republic"` are also accepted.

An unknown name raises {class}`~pyerviss.exceptions.InvalidParameterError`, with a
suggestion when one is close. A country that exists but has no data for the indicator
raises {class}`~pyerviss.exceptions.DataNotFoundError`:

```text
InvalidParameterError: Unknown country 'Itly'; did you mean 'Italy'?
DataNotFoundError: Italy has no SARI data; use pyerviss.list_countries('sari') to see available countries
```

{func}`~pyerviss.list_countries` lists the countries with data for an indicator:

```python
pv.list_countries("sari")
# ['Austria', 'Belgium', 'Croatia', 'Cyprus', 'Estonia', 'Germany', 'Greece', 'Iceland',
#  'Ireland', 'Latvia', 'Lithuania', 'Luxembourg', 'Malta', 'Romania', 'Slovakia', 'Spain']
```

## Weeks and dates

`start` and `end` select a range of weeks, both inclusive. Each accepts an ISO week, an
ISO date or a {class}`datetime.date`; a date selects the week that contains it.

```python
from datetime import date

pv.get_ili(start="2024-W40", end="2025-W20")
pv.get_ili(start="2024-10-01", end="2025-05-18")  # same weeks
pv.get_ili(start=date(2024, 10, 1))               # from 2024-W40 onwards
```

Weeks follow ISO 8601: week 1 is the week containing the year's first Thursday, and some
years have a week 53 (e.g. `2020-W53`). The `date` column is the week's Sunday, so
`2025-W01` is dated 2025-01-05.

## Seasons

A season such as `"2024/25"` runs from week 40 of 2024 to week 39 of 2025: a full year,
including the summer weeks that ERVISS now reports year-round. Pass one season or a list:

```python
pv.get_ili(season="2024/25")
pv.get_ili(season=["2022/23", "2023/24"])
```

`"2024/2025"` is accepted too. A season can't be combined with `start`/`end`.

To restrict to the traditional influenza season (weeks 40 to 20), filter the result:

```python
df = pv.get_ili(season="2024/25")
week = df["year_week"].str[-2:].astype(int)
df = df[(week >= 40) | (week <= 20)]
```

{func}`~pyerviss.list_seasons` lists the seasons with data.

## Age groups

`age_groups` takes one or more of `"0-4"`, `"5-14"`, `"15-64"`, `"65+"` and `"total"`
(all ages combined). By default all age groups are returned.

```python
pv.get_sari(age_groups="65+")
pv.get_ili(age_groups=["0-4", "5-14"])
```

:::{note}
ILI and ARI data before 2022-W25 is only available for `"total"`. See {doc}`data`.
:::

## What is available

{func}`~pyerviss.coverage` summarizes each country's data for an indicator. Coverage
varies a lot: some countries report all years, others stopped or started recently.

```python
pv.coverage("ili")
```

```text
   country country_code first_week last_week  n_weeks                      age_groups    denominator
0  Austria           AT   2014-W40  2026-W14      315  [0-4, 5-14, 15-64, 65+, total]     population
1  Belgium           BE   2014-W40  2026-W38      625  [0-4, 5-14, 15-64, 65+, total]     population
2  Croatia           HR   2014-W40  2026-W37      424  [0-4, 5-14, 15-64, 65+, total]     population
3   Cyprus           CY   2014-W40  2019-W25      242                         [total]  consultations
...
```

`n_weeks` counts weeks with data in any age group; gaps between `first_week` and
`last_week` are common, especially outside the winter season.

{func}`~pyerviss.latest_week` returns the most recent week with data, overall or for one
indicator.
