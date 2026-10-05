# pyerviss

Weekly influenza-like illness (ILI), acute respiratory infection (ARI) and severe acute
respiratory infection (SARI) rates for EU/EEA countries, and test positivity for
influenza, RSV and SARS-CoV-2, as pandas DataFrames.

pyerviss gives Python access to data from [ERVISS](https://erviss.org), the European
Respiratory Virus Surveillance Summary, with ILI and ARI history back to 2014.

:::{important}
pyerviss is an independent, **unofficial** project. It is not affiliated with, endorsed
by, or maintained by the European Centre for Disease Prevention and Control (ECDC) or
ERVISS. The data is processed here (see {doc}`data` and {doc}`units`) and can differ
from the official figures. For official data, see [erviss.org](https://erviss.org).
:::

## Installation

```bash
pip install pyerviss
```

Requires Python 3.10 or later.

## Quickstart

```python
import pyerviss as pv

# ILI rates for Italy and Malta in the 2024/25 season, all ages combined
df = pv.get_ili(countries=["Italy", "MT"], season="2024/25", age_groups="total")
```

```text
  indicator country country_code year_week       date    age  value                    unit
0       ili   Italy           IT  2024-W42 2024-10-20  total  592.8  per 100,000 population
1       ili   Italy           IT  2024-W43 2024-10-27  total  583.4  per 100,000 population
...
```

The first call downloads the data (a few MB) and caches it; later calls are fast and work
offline. See {doc}`querying` for all filters and {doc}`units` before comparing countries.

```{toctree}
:maxdepth: 2
:hidden:

querying
positivity
plotting
units
data
caching
api
```

## Contents

- {doc}`querying`: countries, weeks, seasons, age groups and the output format
- {doc}`positivity`: influenza, RSV and SARS-CoV-2 test positivity, and combining it
  with ILI/ARI/SARI
- {doc}`plotting`: season charts, comparing countries and age groups, positivity with
  confidence bands
- {doc}`units`: what each value measures, by country (read this before comparing
  countries)
- {doc}`data`: where the data comes from, how it is updated and what differs from ECDC
- {doc}`caching`: local cache, updates and offline use
- {doc}`api`: reference for every public function
