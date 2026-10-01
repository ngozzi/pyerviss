"""Indicator definition."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Indicator:
    """A surveillance indicator stored in one of the repository's data files.

    Attributes:
        name: Short name used in the API, e.g. "ili".
        description: Human-readable description.
        data_file: File in the repository's data/ folder that holds the indicator.
        ecdc_indicator: Value of the file's ``indicator`` column for this indicator.
        consultation_countries: Countries whose rates are per 100,000 consultations
            rather than per 100,000 population.
    """

    name: str
    description: str
    data_file: str
    ecdc_indicator: str
    consultation_countries: frozenset[str] = field(default_factory=frozenset)

    def denominator(self, country: str) -> str:
        """Denominator of the rate for a country: "population" or "consultations"."""
        return "consultations" if country in self.consultation_countries else "population"
