from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import cast

from tennis_genome.data.provenance import (
    AllowedUseStatus,
    SourceMetadata,
    assert_research_allowed,
)

_REQUIRED_MANIFEST_FIELDS = {
    "schema_version",
    "source_format",
    "source_filename",
    "source_sha256",
    "source_metadata",
    "tour",
    "row_count",
    "date_min",
    "date_max",
    "pre_match_filename",
    "pre_match_sha256",
    "outcome_filename",
    "outcome_sha256",
}


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_metadata(value: object) -> SourceMetadata:
    if not isinstance(value, dict):
        raise ValueError("manifest source_metadata must be an object")
    source_id = value.get("source_id")
    provider = value.get("provider")
    allowed_use_status = value.get("allowed_use_status", "unknown_do_not_use")
    if not isinstance(source_id, str) or not source_id:
        raise ValueError("manifest source_metadata.source_id is required")
    if not isinstance(provider, str) or not provider:
        raise ValueError("manifest source_metadata.provider is required")
    allowed = {
        "research_allowed",
        "production_allowed",
        "permission_required",
        "unknown_do_not_use",
    }
    if allowed_use_status not in allowed:
        raise ValueError(f"invalid allowed_use_status: {allowed_use_status!r}")
    notes_raw = value.get("notes", [])
    if not isinstance(notes_raw, (list, tuple)):
        raise ValueError("manifest source_metadata.notes must be an array")
    return SourceMetadata(
        source_id=source_id,
        provider=provider,
        source_version=_optional_string(value.get("source_version")),
        license_name=_optional_string(value.get("license_name")),
        license_url=_optional_string(value.get("license_url")),
        allowed_use_status=cast(AllowedUseStatus, allowed_use_status),
        retrieved_at=_optional_string(value.get("retrieved_at")),
        notes=tuple(str(note) for note in notes_raw),
    )


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def verify_canonical_manifest(
    *,
    manifest_path: Path,
    pre_match_path: Path,
    outcome_path: Path,
    stats_path: Path | None = None,
    require_research_permission: bool = True,
) -> dict[str, object]:
    """Verify canonical artifacts against their exact provenance manifest.

    ``stats_path`` is optional for backward compatibility with experiments that
    only consume the pre-match/outcome split. Experiments that depend on
    post-match statistics must pass it explicitly; the verifier then requires
    and validates the stats filename/hash recorded in the manifest.
    """
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("dataset manifest must be a JSON object")
    missing = sorted(_REQUIRED_MANIFEST_FIELDS.difference(manifest))
    if missing:
        raise ValueError(f"dataset manifest missing required fields: {missing}")

    metadata = _source_metadata(manifest["source_metadata"])
    if require_research_permission:
        assert_research_allowed(metadata)

    expected_pre_name = str(manifest["pre_match_filename"])
    expected_outcome_name = str(manifest["outcome_filename"])
    if pre_match_path.name != expected_pre_name:
        raise ValueError(
            f"pre-match filename does not match manifest: {pre_match_path.name!r} != {expected_pre_name!r}"
        )
    if outcome_path.name != expected_outcome_name:
        raise ValueError(
            f"outcome filename does not match manifest: {outcome_path.name!r} != {expected_outcome_name!r}"
        )

    if sha256_file(pre_match_path) != manifest["pre_match_sha256"]:
        raise ValueError("pre-match Parquet hash does not match dataset manifest")
    if sha256_file(outcome_path) != manifest["outcome_sha256"]:
        raise ValueError("outcome Parquet hash does not match dataset manifest")

    if stats_path is not None:
        if "stats_filename" not in manifest or "stats_sha256" not in manifest:
            raise ValueError("dataset manifest does not declare a canonical stats artifact")
        expected_stats_name = str(manifest["stats_filename"])
        if stats_path.name != expected_stats_name:
            raise ValueError(
                f"stats filename does not match manifest: {stats_path.name!r} != {expected_stats_name!r}"
            )
        if sha256_file(stats_path) != manifest["stats_sha256"]:
            raise ValueError("stats Parquet hash does not match dataset manifest")

    return manifest
