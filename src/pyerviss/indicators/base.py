"""Indicator definition."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True)
class Indicator:
    """A surveillance indicator stored in one of the repository's data files.

    Attributes:
        name: Short name used in the API, e.g. "ili".
        description: Human-readable description.
        data_file: File in the repository's data/ folder that holds the indicator.
        ecdc_indicator: Value of the file's ``indicator`` column for this indicator.
        denominator_default: What rates are per 100,000 of, for most countries.
        denominator_exceptions: Countries whose rates use a different denominator.
    """

    name: str
    description: str
    data_file: str
    ecdc_indicator: str
    denominator_default: str = "population"
    denominator_exceptions: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def denominator(self, country: str) -> str:
        """What a country's rates are per 100,000 of, e.g. "population"."""
        return self.denominator_exceptions.get(country, self.denominator_default)
