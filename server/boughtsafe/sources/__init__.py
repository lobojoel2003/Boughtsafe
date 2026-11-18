"""Recall feed adapters."""

from __future__ import annotations

from ..config import Settings
from .base import NormalizedRecall, Source
from .cpsc import CPSCSource
from .fsis import FSISSource
from .openfda import OpenFDASource

SOURCES: dict[str, type[Source]] = {
    "fda": OpenFDASource,
    "fsis": FSISSource,
    "cpsc": CPSCSource,
}

LABELS = {"fda": "FDA", "fsis": "USDA FSIS", "cpsc": "CPSC"}


def build_sources(settings: Settings, names: list[str] | None = None) -> list[Source]:
    return [SOURCES[n](settings) for n in (names or list(SOURCES))]


__all__ = ["LABELS", "SOURCES", "NormalizedRecall", "Source", "build_sources"]
