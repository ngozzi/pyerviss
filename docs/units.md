# Units

Every row has a `unit` column saying what `value` measures. For ILI, ARI and SARI rates
it depends on the indicator and the country, following ECDC's reporting:

| Indicator | Countries | `unit` |
|---|---|---|
| ILI, ARI | all others | `per 100,000 population` |
| ILI, ARI | Finland | `per 100,000 consultations` |
| ILI, ARI | Cyprus, Luxembourg, Malta | `per 100,000 consultations` (ECDC: per 100 consultations; multiplied by 1000) |
| SARI | all others | `per 100,000 population` (hospital catchment population) |
| SARI | Greece, Ireland, Latvia, Luxembourg | `per 100,000 hospital admissions` (ECDC: per 100 total hospital admissions; multiplied by 1000) |
| Positivity | all | `%` of tested samples (see {doc}`positivity`) |

ECDC's notes on the data:

> ILI and ARI consultation rates are calculated per 100 000 population, except for Cyprus,
> Luxembourg, Malta (per 100 consultations) and Finland (per 100 000 consultations).

> SARI rates are calculated per 100 000 hospital catchment population, except for Greece,
> Ireland, Latvia and Luxembourg (per 100 total hospital admissions). Data from Slovakia
> are based on ICU admissions.

## Why some values are multiplied by 1000

ECDC publishes some rates per 100 consultations or admissions, which is a percentage.
pyerviss multiplies these by 1000 so that every rate has the same form, per 100,000.
This matches the convention of the
[European RespiCast Hub](https://github.com/european-modelling-hubs/RespiCast-SyndromicIndicators),
whose historical data pyerviss includes (see {doc}`data`).

So a Malta ILI value of 5800 means 5.8% of consultations were for ILI, which ECDC
publishes as 5.8.

## Comparing countries

:::{warning}
Rates with different units measure different things and are **not directly
comparable**. A rate per 100,000 consultations is the share of GP visits that were for
ILI or ARI; a rate per 100,000 population is visits relative to the population covered.
:::

Even with the same unit, rates depend on each country's surveillance system, case
definitions and catchment, so comparing levels across countries needs care. Trends
within a country are usually more robust.

To keep only one kind of rate, filter on `unit`:

```python
df = pv.get_ili(season="2024/25")
df = df[df["unit"] == "per 100,000 population"]
```

## Slovakia SARI

Slovakia's SARI data counts ICU admissions only, so its rates are much lower than other
countries' (typically below 1 per 100,000) and are not comparable with them. Its unit is
still `per 100,000 population`.

## Unit changes upstream

If ECDC changed a country's unit, every value for that country would shift by the same
large factor. The daily sync compares new data with stored data on the same weeks and
stops, without writing anything, if a series' values shift by more than 100x. A
maintainer then checks ECDC's notes before the data is updated.
