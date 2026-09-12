from __future__ import annotations

import hashlib
import json
from datetime import date

from tennis_genome.data.canonical import HistoricalMatch
from tennis_genome.experiments.pattern_confirm_live_identity import IdentityMapping
from tennis_genome.experiments.pattern_confirm_live_state import (
    ProspectiveStateArtifact,
    build_prospective_state_artifact,
)
from tennis_genome.experiments.pattern_confirm_production import (
    CoreProductionArtifact,
    ProfileProductionArtifact,
)
from tennis_genome.experiments.pattern_confirm_sportradar_crosswalk import (
    crosswalk_mapping,
    verify_crosswalk,
)
from tennis_genome.experiments.pattern_confirm_sportradar_state import (
    history_from_state_bundle,
    target_pre_match,
    verify_state_bundle,
    verify_target_context_artifact,
)

_SOURCE_ID = "CANONICAL_2000_2025_PLUS_SPORTRADAR_TENNIS_V3_STATE_V1"
_BASE_END = date(2025, 12, 31)


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


def training_population_hash(matches: list[HistoricalMatch]) -> str:
    rows = [
        {
            "match_id": match.match_id,
            "event_date": match.pre_match.event_date.isoformat(),
            "outcome_a": match.outcome.a_won,
        }
        for match in matches
    ]
    rows.sort(key=lambda row: (str(row["event_date"]), str(row["match_id"])))
    return _sha256(_canonical_json(rows))


def verified_frozen_base_history(
    base_history: list[HistoricalMatch],
    *,
    profile_artifact: ProfileProductionArtifact,
    core_artifact: CoreProductionArtifact,
) -> list[HistoricalMatch]:
    if profile_artifact.training_end_year != 2025 or core_artifact.training_end_year != 2025:
        raise ValueError("production artifacts do not share the frozen 2025 training cutoff")
    if profile_artifact.training_n != core_artifact.training_n:
        raise ValueError("Profile/Core frozen training counts differ")
    if profile_artifact.training_rows_sha256 != core_artifact.training_rows_sha256:
        raise ValueError("Profile/Core frozen training-row hashes differ")
    if profile_artifact.canonical_manifest_sha256 != core_artifact.canonical_manifest_sha256:
        raise ValueError("Profile/Core canonical manifest hashes differ")
    if profile_artifact.state_semantics != core_artifact.state_semantics:
        raise ValueError("Profile/Core state semantics differ")

    atp = [match for match in base_history if match.pre_match.tour == "ATP"]
    if any(match.pre_match.event_date > _BASE_END for match in atp):
        raise ValueError("frozen base history contains post-2025 ATP rows")
    eligible = [
        match
        for match in atp
        if not match.outcome.walkover and not match.outcome.retirement
    ]
    if len(eligible) != profile_artifact.training_n:
        raise ValueError("frozen base history does not reproduce training N")
    if training_population_hash(eligible) != profile_artifact.training_rows_sha256:
        raise ValueError("frozen base history does not reproduce training-row hash")
    eligible.sort(
        key=lambda match: (
            match.pre_match.event_date,
            match.pre_match.source_order,
            match.match_id,
        )
    )
    return eligible


def build_sportradar_prospective_state(
    *,
    base_history: list[HistoricalMatch],
    state_bundle_payload: dict[str, object],
    target_context_payload: dict[str, object],
    crosswalk_payload: dict[str, object],
    identity_mapping: IdentityMapping,
    profile_artifact: ProfileProductionArtifact,
    core_artifact: CoreProductionArtifact,
) -> ProspectiveStateArtifact:
    base = verified_frozen_base_history(
        base_history,
        profile_artifact=profile_artifact,
        core_artifact=core_artifact,
    )
    sealed_crosswalk = verify_crosswalk(crosswalk_payload)
    crosswalk = crosswalk_mapping(sealed_crosswalk)
    if crosswalk.get(identity_mapping.player_a_sportradar_id) != identity_mapping.player_a_canonical_id:
        raise ValueError("sealed crosswalk does not reproduce target player A identity")
    if crosswalk.get(identity_mapping.player_b_sportradar_id) != identity_mapping.player_b_canonical_id:
        raise ValueError("sealed crosswalk does not reproduce target player B identity")

    bundle = verify_state_bundle(state_bundle_payload, crosswalk=crosswalk)
    target_context = verify_target_context_artifact(
        target_context_payload,
        identity_mapping=identity_mapping,
    )
    target = target_pre_match(target_context)
    extension = history_from_state_bundle(bundle)
    for match in extension:
        if match.pre_match.event_date <= _BASE_END:
            raise ValueError("Sportradar state extension contains a pre-2026 event date")
        if match.pre_match.event_date >= target.event_date:
            raise ValueError(
                "Sportradar state extension is not strictly earlier than target season"
            )

    base_ids = {match.match_id for match in base}
    extension_ids = {match.match_id for match in extension}
    if len(extension_ids) != len(extension):
        raise ValueError("Sportradar state extension contains duplicate match_id values")
    if base_ids & extension_ids:
        raise ValueError("Sportradar extension overlaps frozen base match IDs")

    history_source_sha = _sha256(
        _canonical_json(
            {
                "base_canonical_manifest_sha256": profile_artifact.canonical_manifest_sha256,
                "base_training_rows_sha256": profile_artifact.training_rows_sha256,
                "state_bundle_sha256": bundle.artifact_sha256,
                "crosswalk_sha256": sealed_crosswalk.artifact_sha256,
            }
        )
    )
    return build_prospective_state_artifact(
        history=[*base, *extension],
        target=target,
        history_source_id=_SOURCE_ID,
        history_source_sha256=history_source_sha,
        profile_artifact=profile_artifact,
        core_artifact=core_artifact,
    )
