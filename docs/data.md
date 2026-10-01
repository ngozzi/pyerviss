# Data sources and updates

pyerviss doesn't query ECDC directly. It downloads a mirror kept in the
[pyerviss repository](https://github.com/ngozzi/pyerviss/tree/main/data), which combines
ECDC's current data with history ECDC no longer publishes.

| Indicator | Weeks | Age groups |
|---|---|---|
| ILI | 2014-W40 onwards | all from 2022-W25; `"total"` only before |
| ARI | 2014-W40 onwards | all from 2022-W25; `"total"` only before |
| SARI | 2022-W25 onwards | all |

Coverage varies by country; use {func}`~pyerviss.coverage` to check.

## ECDC data, synced daily

ECDC publishes ERVISS data weekly in
[EU-ECDC/Respiratory_viruses_weekly_data](https://github.com/EU-ECDC/Respiratory_viruses_weekly_data)
(files `ILIARIRates.csv` and `SARIRates.csv`). ECDC's current files start at 2022-W25.

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
- history before 2022-W25 comes from RespiCast;
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
