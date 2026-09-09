from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

AllowedUseStatus = Literal[
    "research_allowed",
    "production_allowed",
    "permission_required",
    "unknown_do_not_use",
]


class SourcePermissionError(ValueError):
    """Raised when a data source is not cleared for the requested use."""


@dataclass(frozen=True)
class SourceMetadata:
    """License/provenance metadata carried with every canonical dataset build."""

    source_id: str
    provider: str
    source_version: str | None = None
    license_name: str | None = None
    license_url: str | None = None
    allowed_use_status: AllowedUseStatus = "unknown_do_not_use"
    retrieved_at: str | None = None
    notes: tuple[str, ...] = ()

    def to_manifest(self) -> dict[str, object]:
        return asdict(self)


def assert_research_allowed(metadata: SourceMetadata) -> None:
    if metadata.allowed_use_status not in {"research_allowed", "production_allowed"}:
        raise SourcePermissionError(
            f"source {metadata.source_id!r} is not cleared for research execution: "
            f"{metadata.allowed_use_status}"
        )


def assert_production_allowed(metadata: SourceMetadata) -> None:
    if metadata.allowed_use_status != "production_allowed":
        raise SourcePermissionError(
            f"source {metadata.source_id!r} is not production-cleared: "
            f"{metadata.allowed_use_status}"
        )
