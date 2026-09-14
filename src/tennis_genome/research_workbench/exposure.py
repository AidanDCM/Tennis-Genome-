from __future__ import annotations

from enum import StrEnum

from pydantic import field_validator

from .contracts import WorkbenchRecord


class ExposureKind(StrEnum):
    """Kinds of information a researcher or procedure may have observed."""

    RAW_OUTCOMES = "RAW_OUTCOMES"
    AGGREGATE_METRIC = "AGGREGATE_METRIC"
    RESIDUAL_ANALYSIS = "RESIDUAL_ANALYSIS"
    FEATURE_SUMMARY = "FEATURE_SUMMARY"
    PROTECTED_RESULT = "PROTECTED_RESULT"
    SOURCE_METADATA = "SOURCE_METADATA"


class ExposureRecord(WorkbenchRecord):
    """Immutable record of information exposure and the decision it may influence."""

    exposure_id: str
    actor: str
    source_ids: tuple[str, ...]
    information_kinds: tuple[ExposureKind, ...]
    description: str
    parent_exposure_ids: tuple[str, ...] = ()
    decision_ids: tuple[str, ...] = ()

    @field_validator("source_ids", "parent_exposure_ids", "decision_ids")
    @classmethod
    def _unique_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("exposure tuple fields must be unique")
        if any(not item.strip() for item in value):
            raise ValueError("exposure tuple fields must not contain blank values")
        return value

    @field_validator("information_kinds")
    @classmethod
    def _unique_kinds(cls, value: tuple[ExposureKind, ...]) -> tuple[ExposureKind, ...]:
        if not value:
            raise ValueError("information_kinds must not be empty")
        if len(set(value)) != len(value):
            raise ValueError("information_kinds must be unique")
        return value


class ExposureGraph:
    """Append-only in-memory dependency graph for adaptive research exposure.

    Parents must already exist when a record is added. This insertion rule makes cycles
    impossible and makes inherited exposure explicit rather than inferential.
    """

    def __init__(self) -> None:
        self._records: dict[str, ExposureRecord] = {}

    def add(self, record: ExposureRecord) -> None:
        existing = self._records.get(record.exposure_id)
        if existing is not None:
            if existing.semantic_sha256 != record.semantic_sha256:
                raise ValueError(
                    f"exposure_id {record.exposure_id!r} already has different content"
                )
            return
        if record.exposure_id in record.parent_exposure_ids:
            raise ValueError("an exposure cannot depend on itself")
        missing = [parent for parent in record.parent_exposure_ids if parent not in self._records]
        if missing:
            raise ValueError("parent exposures must be registered first: " + ", ".join(missing))
        self._records[record.exposure_id] = record

    def get(self, exposure_id: str) -> ExposureRecord:
        try:
            return self._records[exposure_id]
        except KeyError as exc:
            raise KeyError(f"unknown exposure_id {exposure_id!r}") from exc

    def assert_registered(self, exposure_ids: tuple[str, ...]) -> None:
        """Fail closed when a procedure cites exposure records that do not exist."""

        missing = sorted(exposure_id for exposure_id in exposure_ids if exposure_id not in self._records)
        if missing:
            raise ValueError("procedure cites unregistered exposure IDs: " + ", ".join(missing))

    def ancestors(self, exposure_id: str) -> frozenset[str]:
        self.get(exposure_id)
        seen: set[str] = set()
        stack = list(self._records[exposure_id].parent_exposure_ids)
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(self._records[current].parent_exposure_ids)
        return frozenset(seen)

    def inherited_source_ids(self, exposure_id: str) -> frozenset[str]:
        ids = {exposure_id, *self.ancestors(exposure_id)}
        sources: set[str] = set()
        for record_id in ids:
            sources.update(self._records[record_id].source_ids)
        return frozenset(sources)

    def assert_independent(
        self,
        *,
        exposure_ids: tuple[str, ...],
        protected_source_ids: tuple[str, ...],
    ) -> None:
        self.assert_registered(exposure_ids)
        protected = set(protected_source_ids)
        overlaps: dict[str, list[str]] = {}
        for exposure_id in exposure_ids:
            overlap = sorted(self.inherited_source_ids(exposure_id) & protected)
            if overlap:
                overlaps[exposure_id] = overlap
        if overlaps:
            detail = "; ".join(
                f"{exposure_id}: {','.join(source_ids)}"
                for exposure_id, source_ids in sorted(overlaps.items())
            )
            raise ValueError(
                "protected evaluation is not independent of research exposure: " + detail
            )

    def records(self) -> tuple[ExposureRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))
