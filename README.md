# pyerviss

[![CI](https://github.com/ngozzi/pyerviss/actions/workflows/ci.yml/badge.svg)](https://github.com/ngozzi/pyerviss/actions/workflows/ci.yml)

Python API to ERVISS, the European Respiratory Virus Surveillance Summary

## Data

`data/` mirrors ILI, ARI and SARI rates from ECDC's
[Respiratory_viruses_weekly_data](https://github.com/EU-ECDC/Respiratory_viruses_weekly_data),
synced daily and merged cumulatively (rows ECDC removes are kept).

### Units

All ILI and ARI rates are per 100,000, but the denominator differs by country:

| Countries | Unit |
|---|---|
| All others | per 100,000 population |
| Finland | per 100,000 consultations |
| Cyprus, Luxembourg, Malta | per 100,000 consultations (ECDC publishes these per 100 consultations; we multiply by 1000) |

Rates for consultation-based countries are not directly comparable with population-based ones.
SARI rates are stored as published by ECDC. The sync fails if a country's values change scale
by orders of magnitude, which would indicate a unit change upstream.
