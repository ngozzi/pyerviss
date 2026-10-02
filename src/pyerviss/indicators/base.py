"""Indicator definition."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True)
class Indicator:
    """A rate indicator stored in one of the repository's data files.

    Attributes:
        name: Short name used in the API, e.g. "ili".
        description: Human-readable description.
        data_file: File in the repository's data/ folder that holds the indicator.
        ecdc_indicator: Value of the file's ``indicator`` column for this indicator.
        unit_default: Unit of the values for most countries.
        unit_exceptions: Countries whose values use a different unit.
    """

    name: str
    description: str
    data_file: str
    ecdc_indicator: str
    unit_default: str = "per 100,000 population"
    unit_exceptions: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def unit(self, country: str) -> str:
        """Unit of a country's values, e.g. "per 100,000 population"."""
        return self.unit_exceptions.get(country, self.unit_default)
