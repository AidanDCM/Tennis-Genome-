from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, datetime

from tennis_genome.data.canonical import HistoricalMatch
from tennis_genome.experiments.pattern_confirm_live_identity import IdentityMapping
from tennis_genome.experiments.pattern_confirm_live_state import (
    prospective_state_as_dict,
    verify_prospective_state_artifact,
)
from tennis_genome.experiments.pattern_confirm_production import (
    CoreProductionArtifact,
    ProfileProductionArtifact,
)
from tennis_genome.experiments.pattern_confirm_sportradar_client import (
    fetch_competitor_profile,
    fetch_season_info,
    fetch_sport_event_summary,
)
from tennis_genome.experiments.pattern_confirm_sportradar_crosswalk import (
    crosswalk_mapping,
    verify_crosswalk,
)
from tennis_genome.experiments.pattern_confirm_sportradar_pipeline import (
    FROZEN_BASE_HISTORY_CONTENT_SHA256,
    HISTORY_SOURCE_ID,
    build_sportradar_prospective_state,
    history_source_sha256,
    training_content_hash,
)
from tennis_genome.experiments.pattern_confirm_sportradar_state import (
    build_target_context_artifact,
    history_from_state_bundle,
    target_context_as_dict,
    verify_state_bundle,
    verify_target_context_artifact,
)
from tennis_genome.experiments.pattern_confirm_sportradar_state_capture import (
    capture_season_state,
    state_capture_as_dict,
    verify_state_capture,
)

_VERSION = "pattern-confirm-sportradar-source-package-v3"
_STATE_START = date(2026, 1, 1)


@dataclass(frozen=True)
class SportradarSourcePackage:
    version: str
    captured_at: str
    outcome_scope: str
    match_id: str
    sportradar_event_id: str
    season_id: str
    season_start_date: str
    identity_mapping_sha256: str
    crosswalk_sha256: str
    state_capture_sha256: str
    state_bundle_sha256: str
    target_context_sha256: str
    prospective_state_sha256: str
    base_history_content_sha256: str
    selected_season_count: int
    fetched_page_count: int
    fetched_summary_count: int
    cutoff_eligible_summary_count: int
    cutoff_excluded_summary_count: int
    state_accepted_count: int
    state_parser_excluded_count: int
    target_context: dict[str, object]
    state_capture: dict[str, object]
    prospective_state: dict[str, object]
    artifact_sha256: str


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _self_hash(payload: dict[str, object]) -> str:
    unsigned = dict(payload)
    unsigned.pop("artifact_sha256", None)
    return _sha256(_canonical_json(unsigned))


def _capture_time(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("captured_at must be timezone-aware")
    return value.isoformat()


def _verify_capture_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError("source package captured_at must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("source package captured_at must be timezone-aware")
    return parsed


def _nested_state_counts(state_capture: dict[str, object]) -> tuple[int, int]:
    bundle = state_capture.get("state_bundle")
    if not isinstance(bundle, dict):
        raise ValueError("state capture is missing nested state bundle")
    accepted = bundle.get("accepted_count")
    excluded = bundle.get("excluded_count")
    if not isinstance(accepted, int) or not isinstance(excluded, int):
        raise ValueError("state capture nested counts must be integers")
    return accepted, excluded


def build_live_source_package(
    *,
    match_id: str,
    base_history: list[HistoricalMatch],
    identity_mapping: IdentityMapping,
    crosswalk_payload: dict[str, object],
    profile_artifact: ProfileProductionArtifact,
    core_artifact: CoreProductionArtifact,
    api_key: str,
    access_level: str,
    captured_at: datetime,
    get_json: Callable[..., object],
) -> SportradarSourcePackage:
    match_id = str(match_id).strip()
    if not match_id:
        raise ValueError("match_id must be non-empty")
    captured_at_text = _capture_time(captured_at)
    target_date = date.fromisoformat(identity_mapping.season_start_date)
    if target_date < _STATE_START:
        raise ValueError("target season predates the post-2025 state source window")

    sealed_crosswalk = verify_crosswalk(crosswalk_payload)
    summary = fetch_sport_event_summary(
        identity_mapping.sportradar_event_id,
        api_key=api_key,
        access_level=access_level,
        get_json=get_json,
    )
    season_info = fetch_season_info(
        identity_mapping.season_id,
        api_key=api_key,
        access_level=access_level,
        get_json=get_json,
    )
    profile_a = fetch_competitor_profile(
        identity_mapping.player_a_sportradar_id,
        api_key=api_key,
        access_level=access_level,
        get_json=get_json,
    )
    profile_b = fetch_competitor_profile(
        identity_mapping.player_b_sportradar_id,
        api_key=api_key,
        access_level=access_level,
        get_json=get_json,
    )
    target_context = build_target_context_artifact(
        match_id=match_id,
        identity_mapping=identity_mapping,
        summary_payload=summary,
        season_info_payload=season_info,
        profile_a_payload=profile_a,
        profile_b_payload=profile_b,
    )
    target_payload = target_context_as_dict(target_context)

    state_capture = capture_season_state(
        target_cutoff_date=target_date,
        crosswalk_payload=crosswalk_payload,
        api_key=api_key,
        access_level=access_level,
        get_json=get_json,
    )
    state_capture_payload = state_capture_as_dict(state_capture)
    state_accepted_count, state_parser_excluded_count = _nested_state_counts(state_capture_payload)
    uses_frozen_production_history = (
        profile_artifact.artifact_sha256
        == "cc82e93a8465f9430b16316a1f9bf770951631de0aff7d17f8374e5cff523351"
        and core_artifact.artifact_sha256
        == "5097257e2c7e5cf7225b4ce7fd08b405b494766d0c9126427f476fd7b952dbb7"
        and profile_artifact.training_n == 75112
        and core_artifact.training_n == 75112
        and profile_artifact.training_rows_sha256
        == "c2c5b4ddcd30f68d75b98a9b5e460ff71d4601b50115695bb1784c8f5f897d2c"
        and core_artifact.training_rows_sha256
        == "c2c5b4ddcd30f68d75b98a9b5e460ff71d4601b50115695bb1784c8f5f897d2c"
    )
    expected_base_content = (
        FROZEN_BASE_HISTORY_CONTENT_SHA256 if uses_frozen_production_history else None
    )
    prospective_state = build_sportradar_prospective_state(
        base_history=base_history,
        state_capture_payload=state_capture_payload,
        target_context_payload=target_payload,
        crosswalk_payload=crosswalk_payload,
        identity_mapping=identity_mapping,
        profile_artifact=profile_artifact,
        core_artifact=core_artifact,
        expected_base_history_content_sha256=expected_base_content,
    )
    base_eligible = [
        match
        for match in base_history
        if match.pre_match.tour == "ATP"
        and not match.outcome.walkover
        and not match.outcome.retirement
    ]
    base_history_content_sha256 = training_content_hash(base_eligible)
    prospective_payload = prospective_state_as_dict(prospective_state)

    unsigned: dict[str, object] = {
        "version": _VERSION,
        "captured_at": captured_at_text,
        "outcome_scope": (
            "prior completed state only; target/future outcome and settlement are not accessed"
        ),
        "match_id": match_id,
        "sportradar_event_id": identity_mapping.sportradar_event_id,
        "season_id": identity_mapping.season_id,
        "season_start_date": identity_mapping.season_start_date,
        "identity_mapping_sha256": identity_mapping.artifact_sha256,
        "crosswalk_sha256": sealed_crosswalk.artifact_sha256,
        "state_capture_sha256": state_capture.artifact_sha256,
        "state_bundle_sha256": state_capture.state_bundle_sha256,
        "target_context_sha256": target_context.artifact_sha256,
        "prospective_state_sha256": prospective_state.artifact_sha256,
        "base_history_content_sha256": base_history_content_sha256,
        "selected_season_count": state_capture.selected_season_count,
        "fetched_page_count": state_capture.fetched_page_count,
        "fetched_summary_count": state_capture.fetched_summary_count,
        "cutoff_eligible_summary_count": state_capture.cutoff_eligible_summary_count,
        "cutoff_excluded_summary_count": state_capture.cutoff_excluded_summary_count,
        "state_accepted_count": state_accepted_count,
        "state_parser_excluded_count": state_parser_excluded_count,
        "target_context": target_payload,
        "state_capture": state_capture_payload,
        "prospective_state": prospective_payload,
    }
    return SportradarSourcePackage(
        **unsigned,
        artifact_sha256=_self_hash(unsigned),
    )


def source_package_as_dict(package: SportradarSourcePackage) -> dict[str, object]:
    return asdict(package)


def verify_source_package(
    payload: dict[str, object],
    *,
    identity_mapping: IdentityMapping,
    crosswalk_payload: dict[str, object],
    profile_artifact: ProfileProductionArtifact,
    core_artifact: CoreProductionArtifact,
) -> SportradarSourcePackage:
    if str(payload.get("artifact_sha256", "")) != _self_hash(payload):
        raise ValueError("Sportradar source package digest mismatch")
    package = SportradarSourcePackage(**payload)
    if package.version != _VERSION:
        raise ValueError("unexpected Sportradar source package version")
    _verify_capture_time(package.captured_at)
    if "target/future outcome" not in package.outcome_scope:
        raise ValueError("source package outcome scope is not frozen")
    if package.identity_mapping_sha256 != identity_mapping.artifact_sha256:
        raise ValueError("source package identity mapping mismatch")
    if package.match_id != str(package.target_context.get("match_id", "")):
        raise ValueError("source package target match identity mismatch")
    if package.match_id != str(package.prospective_state.get("match_id", "")):
        raise ValueError("source package prospective-state match identity mismatch")
    if package.sportradar_event_id != identity_mapping.sportradar_event_id:
        raise ValueError("source package Sportradar event mismatch")
    if package.season_id != identity_mapping.season_id:
        raise ValueError("source package season mismatch")
    if package.season_start_date != identity_mapping.season_start_date:
        raise ValueError("source package season-start mismatch")

    if profile_artifact.training_n != core_artifact.training_n:
        raise ValueError("source package Profile/Core frozen training counts differ")
    if profile_artifact.training_rows_sha256 != core_artifact.training_rows_sha256:
        raise ValueError("source package Profile/Core training-row hashes differ")
    if profile_artifact.canonical_manifest_sha256 != core_artifact.canonical_manifest_sha256:
        raise ValueError("source package Profile/Core canonical manifest hashes differ")
    if len(package.base_history_content_sha256) != 64 or any(
        char not in "0123456789abcdef" for char in package.base_history_content_sha256
    ):
        raise ValueError("source package base-history content hash is invalid")
    uses_frozen_production_history = (
        profile_artifact.artifact_sha256
        == "cc82e93a8465f9430b16316a1f9bf770951631de0aff7d17f8374e5cff523351"
        and core_artifact.artifact_sha256
        == "5097257e2c7e5cf7225b4ce7fd08b405b494766d0c9126427f476fd7b952dbb7"
        and profile_artifact.training_n == 75112
        and core_artifact.training_n == 75112
        and profile_artifact.training_rows_sha256
        == "c2c5b4ddcd30f68d75b98a9b5e460ff71d4601b50115695bb1784c8f5f897d2c"
        and core_artifact.training_rows_sha256
        == "c2c5b4ddcd30f68d75b98a9b5e460ff71d4601b50115695bb1784c8f5f897d2c"
    )
    if (
        uses_frozen_production_history
        and package.base_history_content_sha256 != FROZEN_BASE_HISTORY_CONTENT_SHA256
    ):
        raise ValueError("source package does not bind the frozen base-history content")

    sealed_crosswalk = verify_crosswalk(crosswalk_payload)
    if package.crosswalk_sha256 != sealed_crosswalk.artifact_sha256:
        raise ValueError("source package crosswalk mismatch")
    target = verify_target_context_artifact(
        package.target_context,
        identity_mapping=identity_mapping,
    )
    capture = verify_state_capture(
        package.state_capture,
        crosswalk_payload=crosswalk_payload,
    )
    state = verify_prospective_state_artifact(
        package.prospective_state,
        profile_artifact=profile_artifact,
        core_artifact=core_artifact,
    )
    if package.target_context_sha256 != target.artifact_sha256:
        raise ValueError("source package target-context hash mismatch")
    if package.state_capture_sha256 != capture.artifact_sha256:
        raise ValueError("source package state-capture hash mismatch")
    if package.state_bundle_sha256 != capture.state_bundle_sha256:
        raise ValueError("source package state-bundle hash mismatch")
    if package.prospective_state_sha256 != state.artifact_sha256:
        raise ValueError("source package prospective-state hash mismatch")
    if capture.target_state_cutoff_date != package.season_start_date:
        raise ValueError("source package state cutoff mismatch")

    expected_history_source_sha = history_source_sha256(
        base_canonical_manifest_sha256=profile_artifact.canonical_manifest_sha256,
        base_training_rows_sha256=profile_artifact.training_rows_sha256,
        base_history_content_sha256=package.base_history_content_sha256,
        state_capture_sha256=capture.artifact_sha256,
        state_bundle_sha256=capture.state_bundle_sha256,
        target_context_sha256=target.artifact_sha256,
        crosswalk_sha256=sealed_crosswalk.artifact_sha256,
    )
    if state.history_source_id != HISTORY_SOURCE_ID:
        raise ValueError("prospective state history source ID is not frozen")
    if state.history_source_sha256 != expected_history_source_sha:
        raise ValueError("prospective state history source provenance mismatch")

    crosswalk = crosswalk_mapping(sealed_crosswalk)
    bundle = verify_state_bundle(capture.state_bundle, crosswalk=crosswalk)
    extension = history_from_state_bundle(bundle)
    eligible_extension_n = sum(
        not match.outcome.walkover and not match.outcome.retirement for match in extension
    )
    expected_history_n = profile_artifact.training_n + eligible_extension_n
    if state.history_n != expected_history_n:
        raise ValueError("prospective state history_n does not match frozen source package")

    state_accepted_count, state_parser_excluded_count = _nested_state_counts(package.state_capture)
    expected_counts = (
        capture.selected_season_count,
        capture.fetched_page_count,
        capture.fetched_summary_count,
        capture.cutoff_eligible_summary_count,
        capture.cutoff_excluded_summary_count,
        state_accepted_count,
        state_parser_excluded_count,
    )
    actual_counts = (
        package.selected_season_count,
        package.fetched_page_count,
        package.fetched_summary_count,
        package.cutoff_eligible_summary_count,
        package.cutoff_excluded_summary_count,
        package.state_accepted_count,
        package.state_parser_excluded_count,
    )
    if actual_counts != expected_counts:
        raise ValueError("source package state-capture accounting mismatch")
    return package
