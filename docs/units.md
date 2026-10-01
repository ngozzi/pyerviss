# Units and denominators

Every `value` is a rate **per 100,000 of the row's `denominator`**. The denominator depends
on the indicator and the country, following ECDC's reporting.

| Indicator | Countries | `denominator` | Unit |
|---|---|---|---|
| ILI, ARI | all others | `population` | per 100,000 population |
| ILI, ARI | Finland | `consultations` | per 100,000 consultations |
| ILI, ARI | Cyprus, Luxembourg, Malta | `consultations` | per 100,000 consultations (ECDC: per 100 consultations; multiplied by 1000) |
| SARI | all others | `population` | per 100,000 hospital catchment population |
| SARI | Greece, Ireland, Latvia, Luxembourg | `admissions` | per 100,000 hospital admissions (ECDC: per 100 total hospital admissions; multiplied by 1000) |

ECDC's notes on the data:

> ILI and ARI consultation rates are calculated per 100 000 population, except for Cyprus,
> Luxembourg, Malta (per 100 consultations) and Finland (per 100 000 consultations).

> SARI rates are calculated per 100 000 hospital catchment population, except for Greece,
> Ireland, Latvia and Luxembourg (per 100 total hospital admissions). Data from Slovakia
> are based on ICU admissions.

## Why some values are multiplied by 1000

ECDC publishes some series per 100 consultations or admissions, which is a percentage.
pyerviss multiplies these by 1000 so that every value has the same form, per 100,000 of
its denominator. This matches the convention of the
[European RespiCast Hub](https://github.com/european-modelling-hubs/RespiCast-SyndromicIndicators),
whose historical data pyerviss includes (see {doc}`data`).

So a Malta ILI value of 5800 means 5.8% of consultations were for ILI, which ECDC
publishes as 5.8.

## Comparing countries

:::{warning}
Rates with different denominators measure different things and are **not directly
comparable**. A rate per 100,000 consultations is the share of GP visits that were for
ILI or ARI; a rate per 100,000 population is visits relative to the population covered.
:::

Even within the same denominator, rates depend on each country's surveillance system,
case definitions and catchment, so comparing levels across countries needs care. Trends
within a country are usually more robust.

To keep only one kind of rate, filter on `denominator`:

```python
df = pv.get_ili(season="2024/25")
df = df[df["denominator"] == "population"]
```

## Slovakia SARI

Slovakia's SARI data counts ICU admissions only, so its rates are much lower than other
countries' (typically below 1 per 100,000) and are not comparable with them. Its
denominator is still `population`.

## Unit changes upstream

If ECDC changed a country's unit, every value for that country would shift by the same
large factor. The daily sync compares new data with stored data on the same weeks and
stops, without writing anything, if a country's values shift by more than 100x. A
maintainer then checks ECDC's notes before the data is updated.
