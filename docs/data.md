# Data sources and updates

pyerviss doesn't query ECDC directly. It downloads a mirror kept in the
[pyerviss repository](https://github.com/ngozzi/pyerviss/tree/main/data), which combines
ECDC's current data with history ECDC no longer publishes.

| Indicator | Weeks | Age groups |
|---|---|---|
| ILI | 2014-W40 onwards | all for most countries; some only `"total"` before 2022-W25 |
| ARI | 2014-W40 onwards | all for most countries; some only `"total"` before 2022-W25 |
| SARI | 2020-W40 onwards | all |
| Positivity, primary care | 2014-W25 onwards (RSV 2016-W40, SARS-CoV-2 2020-W03) | `"total"` |
| Positivity, hospital | 2020-W40 onwards | `"total"` |

Coverage varies by country; use {func}`~pyerviss.coverage` to check.

## ECDC data, synced daily

ECDC publishes ERVISS data weekly in
[EU-ECDC/Respiratory_viruses_weekly_data](https://github.com/EU-ECDC/Respiratory_viruses_weekly_data)
(files `ILIARIRates.csv`, `SARIRates.csv`, `sentinelTestsDetectionsPositivity.csv` and
`SARITestsDetectionsPositivity.csv`). ECDC's current files start at 2022-W25.

A scheduled job checks for new data every day at 18:17 UTC and merges it into the mirror:

- rows are matched on country, week, indicator and age group;
- **ECDC's value wins** when a row exists in both, so ECDC's revisions of past weeks are
  picked up;
- **rows ECDC removes are kept**, so the mirror only grows;
- per-100 rates are converted to per 100,000 (see {doc}`units`);
- the new data is validated before anything is written, and nothing is written if a
  country's values change scale (a likely unit change upstream).

ECDC updates its data weekly, on varying days. Values for recent weeks are often revised
in later weeks as more reports come in.

## History from ECDC's earlier files (2014–2022)

ECDC's files only cover recent seasons, and ECDC drops older weeks from time to time.
Its git history still has every earlier version of each file, so the weeks ECDC has
since dropped were imported once from those versions:

| File | Imported weeks |
|---|---|
| ILI and ARI rates | 2014-W40 to 2022-W24, by age group (`"total"` came from RespiCast, below) |
| Primary care virology | 2014-W25 to 2022-W24 |
| SARI rates and virology | 2020-W40 to 2022-W24 (ECDC started publishing SARI data in November 2024, already starting at 2020-W40) |

How the import works:

- each row's value comes from the most recent ECDC version that still had it, so later
  revisions are included;
- only weeks before ECDC's current window were imported; rows ECDC removed within its
  window (withdrawn series, categories it no longer uses) were not;
- values were converted and checked for unit changes like the daily sync. Until
  2025-10-24, ECDC published Greece and Latvia SARI rates per 100,000 hospital
  admissions rather than per 100, so those versions were not multiplied by 1000;
- rate series that were all zeros (Denmark ARI, Malta ARI for 2014-W41 to 2015-W20)
  were left out as missing data.

ECDC keeps revising past weeks while they are in its window. An imported week has the
value ECDC last published before dropping it, so revisions ECDC made to neighbouring
weeks after that are not reflected (for example SARI rates for 2020-W40 to 2021-W24
were last published in May 2025).

## History from RespiCast (2014–2022)

ILI and ARI rates from 2014-W40 for the `"total"` age group were imported once from the
ERVISS snapshots of 2024-10-11 published by the
[European RespiCast Hub](https://github.com/european-modelling-hubs/RespiCast-SyndromicIndicators).
The import only filled weeks missing from ECDC's data; where both had a value, ECDC's was
kept.

This adds about 13,400 rows, including some weeks within ECDC's period that ECDC no longer
publishes (for example Norway ILI for the 2023/24 season). Malta ARI for 2014-W41 to
2015-W20 was left out: every value was 0, which indicates missing data rather than real
zeros. Zeros elsewhere were kept as published.

## Differences from ECDC's data

Because of the above, pyerviss data can differ from what ECDC publishes:

- some values are multiplied by 1000 ({doc}`units`);
- history before 2022-W25 comes from ECDC's earlier files and RespiCast;
- rows ECDC has since removed are still present;
- a revision by ECDC appears after the next daily sync, and in your session after the
  cache's next update check ({doc}`caching`).

For official figures, use [erviss.org](https://erviss.org).

## Metadata

The mirror includes `metadata.json` with the date of the last change, the ECDC commit it
was synced from, row counts, week ranges, units and sources:

```python
from pyerviss.data_loader import get_metadata

get_metadata()["last_update"]  # e.g. "2026-10-01"
```

## Terms of use

The data is ECDC's; see the terms in
[ECDC's repository](https://github.com/EU-ECDC/Respiratory_viruses_weekly_data). The
pyerviss code is MIT licensed.
