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
)
from tennis_genome.experiments.pattern_confirm_production import (
    CoreProductionArtifact,
    ProfileProductionArtifact,
)
from tennis_genome.experiments.pattern_confirm_sportradar_client import (
    fetch_competitor_profile,
    fetch_daily_summary_range,
    fetch_season_info,
    fetch_sport_event_summary,
)
from tennis_genome.experiments.pattern_confirm_sportradar_crosswalk import (
    crosswalk_mapping,
    verify_crosswalk,
)
from tennis_genome.experiments.pattern_confirm_sportradar_pipeline import (
    build_sportradar_prospective_state,
)
from tennis_genome.experiments.pattern_confirm_sportradar_state import (
    build_state_bundle,
    build_target_context_artifact,
    state_bundle_as_dict,
    target_context_as_dict,
)

_VERSION = "pattern-confirm-sportradar-source-package-v1"
_STATE_START = date(2026, 1, 1)


@dataclass(frozen=True)
class SportradarSourcePackage:
    version: str
    captured_at: str
    outcome_scope: str
    sportradar_event_id: str
    season_id: str
    season_start_date: str
    identity_mapping_sha256: str
    crosswalk_sha256: str
    state_bundle_sha256: str
    target_context_sha256: str
    prospective_state_sha256: str
    state_source_count: int
    state_accepted_count: int
    state_excluded_count: int
    target_context: dict[str, object]
    state_bundle: dict[str, object]
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


def build_live_source_package(
    *,
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
    target_date = date.fromisoformat(identity_mapping.season_start_date)
    if target_date < _STATE_START:
        raise ValueError("target season predates the post-2025 state source window")

    sealed_crosswalk = verify_crosswalk(crosswalk_payload)
    crosswalk = crosswalk_mapping(sealed_crosswalk)
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
        match_id=identity_mapping.market_event_id,
        identity_mapping=identity_mapping,
        summary_payload=summary,
        season_info_payload=season_info,
        profile_a_payload=profile_a,
        profile_b_payload=profile_b,
    )

    prior_summaries = fetch_daily_summary_range(
        _STATE_START,
        target_date,
        api_key=api_key,
        access_level=access_level,
        get_json=get_json,
    )
    state_bundle = build_state_bundle(summaries=prior_summaries, crosswalk=crosswalk)
    state_payload = state_bundle_as_dict(state_bundle)
    target_payload = target_context_as_dict(target_context)
    prospective_state = build_sportradar_prospective_state(
        base_history=base_history,
        state_bundle_payload=state_payload,
        target_context_payload=target_payload,
        crosswalk_payload=crosswalk_payload,
        identity_mapping=identity_mapping,
        profile_artifact=profile_artifact,
        core_artifact=core_artifact,
    )
    prospective_payload = prospective_state_as_dict(prospective_state)

    unsigned: dict[str, object] = {
        "version": _VERSION,
        "captured_at": _capture_time(captured_at),
        "outcome_scope": (
            "prior completed state only; target/future outcome and settlement are not accessed"
        ),
        "sportradar_event_id": identity_mapping.sportradar_event_id,
        "season_id": identity_mapping.season_id,
        "season_start_date": identity_mapping.season_start_date,
        "identity_mapping_sha256": identity_mapping.artifact_sha256,
        "crosswalk_sha256": sealed_crosswalk.artifact_sha256,
        "state_bundle_sha256": state_bundle.artifact_sha256,
        "target_context_sha256": target_context.artifact_sha256,
        "prospective_state_sha256": prospective_state.artifact_sha256,
        "state_source_count": state_bundle.source_count,
        "state_accepted_count": state_bundle.accepted_count,
        "state_excluded_count": state_bundle.excluded_count,
        "target_context": target_payload,
        "state_bundle": state_payload,
        "prospective_state": prospective_payload,
    }
    return SportradarSourcePackage(
        **unsigned,
        artifact_sha256=_self_hash(unsigned),
    )


def source_package_as_dict(package: SportradarSourcePackage) -> dict[str, object]:
    return asdict(package)


def verify_source_package(payload: dict[str, object]) -> SportradarSourcePackage:
    if str(payload.get("artifact_sha256", "")) != _self_hash(payload):
        raise ValueError("Sportradar source package digest mismatch")
    package = SportradarSourcePackage(**payload)
    if package.version != _VERSION:
        raise ValueError("unexpected Sportradar source package version")
    if "target/future outcome" not in package.outcome_scope:
        raise ValueError("source package outcome scope is not frozen")
    if package.state_bundle_sha256 != str(package.state_bundle.get("artifact_sha256", "")):
        raise ValueError("source package state-bundle hash mismatch")
    if package.target_context_sha256 != str(
        package.target_context.get("artifact_sha256", "")
    ):
        raise ValueError("source package target-context hash mismatch")
    if package.prospective_state_sha256 != str(
        package.prospective_state.get("artifact_sha256", "")
    ):
        raise ValueError("source package prospective-state hash mismatch")
    return package
