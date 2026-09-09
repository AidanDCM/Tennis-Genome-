from __future__ import annotations

from pathlib import Path
from typing import Protocol

from tennis_genome.data.canonical import HistoricalMatch, Tour
from tennis_genome.data.provenance import SourceMetadata


class HistoricalMatchSource(Protocol):
    """Provider-neutral boundary for historical match ingestion.

    Adapters may read CSV, API responses, databases, or licensed vendor exports,
    but downstream modeling code consumes only canonical HistoricalMatch records
    plus explicit SourceMetadata.
    """

    @property
    def metadata(self) -> SourceMetadata: ...

    def load(self) -> list[HistoricalMatch]: ...


class SackmannCsvSource:
    """Local research-format adapter behind the provider-neutral interface."""

    def __init__(self, *, path: Path, tour: Tour, metadata: SourceMetadata) -> None:
        self.path = path
        self.tour = tour
        self._metadata = metadata

    @property
    def metadata(self) -> SourceMetadata:
        return self._metadata

    def load(self) -> list[HistoricalMatch]:
        # Local import avoids making the generic source contract depend on pandas.
        from tennis_genome.data.sackmann import load_sackmann_csv

        return load_sackmann_csv(self.path, tour=self.tour)
