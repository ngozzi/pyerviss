# Positivity

{func}`~pyerviss.get_positivity` returns weekly **test positivity**: the percentage of
tested samples that were positive for influenza, RSV or SARS-CoV-2.

```python
import pyerviss as pv

df = pv.get_positivity(
    pathogen="influenza", setting="primary care", countries="Italy", season="2024/25"
)
df[["setting", "pathogen", "country", "year_week", "value", "unit", "tests", "detections"]]
```

```text
        setting   pathogen country year_week  value unit  tests  detections
6  primary care  Influenza   Italy  2024-W52   28.3    %    120          34
7  primary care  Influenza   Italy  2025-W01   39.0    %    267         104
8  primary care  Influenza   Italy  2025-W02   42.8    %    549         235
9  primary care  Influenza   Italy  2025-W03   47.1    %    715         337
...
```

The full columns are `indicator` (`"positivity"`), `setting`, `pathogen`, `country`,
`country_code`, `year_week`, `date`, `age`, `value`, `unit`, `tests` and `detections`.
Data is available from 2022-W25, for all ages combined (`age` is always `"total"`).

## Settings

| `setting` | Samples from | Pairs with |
|---|---|---|
| `"primary care"` | patients with ILI and/or ARI seen by sentinel GPs | {func}`~pyerviss.get_ili`, {func}`~pyerviss.get_ari` |
| `"hospital"` | SARI patients in sentinel hospitals | {func}`~pyerviss.get_sari` |

By default both settings are returned. Primary care positivity is not split by
syndrome: depending on the country, sentinel GPs swab ILI patients, ARI patients or both.

## Pathogens

`pathogen` takes `"influenza"`, `"rsv"` or `"sars-cov-2"` (case-insensitive; `"flu"` and
`"covid"` also work), or a list. By default all three are returned; the `pathogen`
column uses ECDC's names: `"Influenza"`, `"RSV"`, `"SARS-CoV-2"`.

Positivity is published for influenza overall, not by type or subtype (A(H1)pdm09,
A(H3), B/Victoria). Subtype data is not available in pyerviss yet.

## Tests and detections

`value` is `detections / tests × 100`, and both counts are returned alongside it.
**Use them**: many weeks rest on few tests, and positivity from a handful of samples is
noise. A week with 1 test and 1 positive has a positivity of 100%.

```python
df = pv.get_positivity(pathogen="rsv")
df = df[df["tests"] >= 20]  # drop weeks with fewer than 20 tests
```

Weeks with tests but no positivity (for example zero tests) are not returned.

## EU/EEA aggregate

ECDC also publishes positivity for the EU/EEA as a whole. Query it like a country, as
`"EU/EEA"` or with the code `"EU"`:

```python
pv.get_positivity(countries="EU", pathogen="influenza", setting="primary care")
```

## Combining with ILI: pathogen-specific activity

Multiplying the ILI rate by influenza positivity in the same week estimates the
**influenza-attributable ILI rate** (often called "ILI+"), a common signal for tracking
and forecasting influenza:

```python
ili = pv.get_ili(countries="Italy", season="2024/25", age_groups="total")
pos = pv.get_positivity(
    pathogen="influenza", setting="primary care", countries="Italy", season="2024/25"
)

df = ili.merge(pos[["year_week", "value", "tests"]], on="year_week", suffixes=("", "_positivity"))
df["ili_plus"] = df["value"] * df["value_positivity"] / 100
```

```text
  year_week   value  value_positivity  tests  ili_plus
6  2024-W52  1050.8              28.3    120     297.4
7  2025-W01  1234.9              39.0    267     481.6
8  2025-W02  1493.5              42.8    549     639.2
9  2025-W03  1602.0              47.1    715     754.5
...
```

The same works for ARI with RSV or SARS-CoV-2, and for SARI with hospital positivity.

:::{note}
This is an approximation: primary care samples come from ILI and/or ARI patients
depending on the country, and sampling is not always representative of all consultations.
Weeks with few tests make the estimate noisy.
:::

## What is available

```python
pv.coverage("positivity")       # per setting, pathogen and country
pv.list_countries("positivity")
pv.latest_week("positivity")
```

```text
         setting    pathogen country country_code first_week last_week  n_weeks unit
3       hospital   Influenza  EU/EEA           EU   2022-W25  2026-W39      223    %
...
62  primary care   Influenza   Italy           IT   2022-W34  2026-W09       93    %
```
