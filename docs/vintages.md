# Past vintages (backtesting)

ECDC revises recent weeks for a while after first publishing them, often by 10–20%.
To evaluate a forecast fairly, you need the data as it was when the forecast would have
been made, not today's revised values. Pass `as_of` to any query function:

```python
import pyerviss as pv

# ILI rates as ECDC published them on 6 December 2024
df = pv.get_ili(countries="Italy", age_groups="total", as_of="2024-12-06")
```

```text
    indicator country country_code year_week       date    age  value                    unit    vintage
...
284       ili   Italy           IT  2024-W46 2024-11-17  total  718.6  per 100,000 population 2024-12-06
285       ili   Italy           IT  2024-W47 2024-11-24  total  777.3  per 100,000 population 2024-12-06
```

Today the same weeks read 738.0 and 801.1. `as_of` works with {func}`~pyerviss.get_ili`,
{func}`~pyerviss.get_ari`, {func}`~pyerviss.get_sari`, {func}`~pyerviss.get_data`,
{func}`~pyerviss.get_positivity`, {func}`~pyerviss.coverage` and
{func}`~pyerviss.latest_week`. It takes a date or a `"YYYY-MM-DD"` string.

A typical backtest loops over ECDC's publication dates:

```python
for as_of in pv.list_vintages("ili"):
    train = pv.get_ili(countries="Italy", age_groups="total", as_of=as_of)
    ...  # fit, forecast, compare with later data
```

## Where the data comes from

Every week it publishes, ECDC also saves a dated copy of each file (a *snapshot*) in
the `data/snapshots/` folder of its
[repository](https://github.com/EU-ECDC/Respiratory_viruses_weekly_data/tree/main/data/snapshots).
For a given `as_of`, pyerviss uses the latest snapshot dated on or before it.

| Data | First snapshot |
|---|---|
| ILI and ARI | 2023-11-24 |
| Positivity, primary care | 2023-12-01 |
| SARI and positivity, hospital | 2024-11-08 |

{func}`~pyerviss.list_vintages` lists the available dates. ECDC skipped some weeks
(the longest gap runs from 2026-05-22 to 2026-08-07); if the snapshot used is more than
14 days older than `as_of`, you get a warning.

Snapshots only cover ECDC's window of recent seasons at the time. Older weeks come from
the mirror ({doc}`data`), but only weeks older than the snapshot's first week for the
same country, indicator and age group (for positivity: the same pathogen), so a value
ECDC back-filled later can't leak in. Weeks this old are rarely revised.

## The vintage column

With `as_of`, results have an extra last column, `vintage`: the date of the snapshot a
row comes from, or `NaT` for the older weeks taken from the mirror.

## Dates before the first snapshot

For an `as_of` before the first snapshot, there is no record of what was published.
pyerviss returns current data, restricted to the weeks ECDC would have published by
then (a week counts as published on the Friday after it ends), with `vintage` `NaT`
and a warning: values include later revisions.

## Units

Snapshots keep ECDC's original units. pyerviss converts them like the mirror (see
{doc}`units`): per-100 rates are multiplied by 1000. ECDC published Greece and Latvia
SARI already per 100,000 hospital admissions until 2025-10-24, so snapshots from before
that date are not converted for them.

## Downloads and caching

Each snapshot is about 2.5 MB. Only the snapshots you query are downloaded, once: they
never change, so they stay in the cache ({doc}`caching`) until you call
{func}`~pyerviss.clear_cache`. A backtest over 50 weekly dates of ILI data downloads
about 125 MB.

The list of snapshots is read from the GitHub API at most once an hour. GitHub allows
60 unauthenticated requests per hour; set the `GITHUB_TOKEN` environment variable to a
GitHub token if you hit the limit.
