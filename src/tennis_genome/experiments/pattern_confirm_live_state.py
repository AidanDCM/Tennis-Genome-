from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import date

from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, PreMatchState
from tennis_genome.experiments.pattern_confirm_production import (
    CoreProductionArtifact,
    ProfileProductionArtifact,
    core_probability_from_artifact,
    profile_gap_from_artifact,
)
from tennis_genome.features.foundational import (
    FoundationalSnapshot,
    walk_forward_foundational_features,
)
from tennis_genome.profiles.state import (
    MatchProfilePair,
    PlayerProfileSnapshot,
    walk_forward_player_profiles,
)

_VERSION = "pattern-confirm-live-state-v1"
_TOUR = "ATP"


@dataclass(frozen=True)
class ProspectiveStateArtifact:
    version: str
    tour: str
    match_id: str
    event_date: str
    history_source_id: str
    history_source_sha256: str
    history_n: int
    history_rows_sha256: str
    profile_model_sha256: str
    core_model_sha256: str
    target_pre_match: dict[str, object]
    profile_pair: dict[str, object]
    foundational_snapshot: dict[str, object]
    profile_gap: float
    core_probability_a: float
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


def _sha_field(value: str, *, field: str) -> str:
    digest = str(value).strip().lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")
    return digest


def _pre_match_as_dict(state: PreMatchState) -> dict[str, object]:
    payload = asdict(state)
    payload["event_date"] = state.event_date.isoformat()
    return payload


def _pre_match_from_dict(payload: dict[str, object]) -> PreMatchState:
    normalized = dict(payload)
    normalized["event_date"] = date.fromisoformat(str(payload["event_date"]))
    return PreMatchState(**normalized)


def _player_profile_as_dict(snapshot: PlayerProfileSnapshot) -> dict[str, object]:
    payload = asdict(snapshot)
    payload["valid_from"] = snapshot.valid_from.isoformat()
    payload["valid_until"] = (
        snapshot.valid_until.isoformat() if snapshot.valid_until is not None else None
    )
    return payload


def _player_profile_from_dict(payload: dict[str, object]) -> PlayerProfileSnapshot:
    normalized = dict(payload)
    normalized["valid_from"] = date.fromisoformat(str(payload["valid_from"]))
    valid_until = payload.get("valid_until")
    normalized["valid_until"] = (
        None if valid_until is None else date.fromisoformat(str(valid_until))
    )
    return PlayerProfileSnapshot(**normalized)


def _profile_pair_as_dict(pair: MatchProfilePair) -> dict[str, object]:
    return {
        "match_id": pair.match_id,
        "event_date": pair.event_date.isoformat(),
        "player_a": _player_profile_as_dict(pair.player_a),
        "player_b": _player_profile_as_dict(pair.player_b),
    }


def _profile_pair_from_dict(payload: dict[str, object]) -> MatchProfilePair:
    player_a = payload.get("player_a")
    player_b = payload.get("player_b")
    if not isinstance(player_a, dict) or not isinstance(player_b, dict):
        raise ValueError("profile_pair players must be objects")
    return MatchProfilePair(
        match_id=str(payload["match_id"]),
        event_date=date.fromisoformat(str(payload["event_date"])),
        player_a=_player_profile_from_dict(player_a),
        player_b=_player_profile_from_dict(player_b),
    )


def _foundational_as_dict(snapshot: FoundationalSnapshot) -> dict[str, object]:
    payload = asdict(snapshot)
    payload["event_date"] = snapshot.event_date.isoformat()
    return payload


def _foundational_from_dict(payload: dict[str, object]) -> FoundationalSnapshot:
    normalized = dict(payload)
    normalized["event_date"] = date.fromisoformat(str(payload["event_date"]))
    return FoundationalSnapshot(**normalized)


def _historical_match_payload(match: HistoricalMatch) -> dict[str, object]:
    return {
        "pre_match": _pre_match_as_dict(match.pre_match),
        "outcome": asdict(match.outcome),
        "stats": None if match.stats is None else asdict(match.stats),
    }


def _legal_history(history: list[HistoricalMatch], target_date: date) -> list[HistoricalMatch]:
    ids: set[str] = set()
    legal: list[HistoricalMatch] = []
    for match in history:
        if match.pre_match.tour != _TOUR:
            raise ValueError("prospective state history is ATP only")
        if match.match_id in ids:
            raise ValueError("prospective state history contains duplicate match_id")
        ids.add(match.match_id)
        if match.pre_match.event_date >= target_date:
            raise ValueError("prospective state history must be strictly earlier than target date")
        if match.outcome.walkover or match.outcome.retirement:
            continue
        legal.append(match)
    legal.sort(
        key=lambda item: (item.pre_match.event_date, item.pre_match.source_order, item.match_id)
    )
    return legal


def _history_rows_hash(history: list[HistoricalMatch]) -> str:
    rows = [_historical_match_payload(match) for match in history]
    return _sha256(_canonical_json(rows))


def _target_sentinel(target: PreMatchState) -> HistoricalMatch:
    return HistoricalMatch(
        pre_match=target,
        outcome=MatchOutcome(
            match_id=target.match_id,
            a_won=False,
            score=None,
            retirement=False,
            walkover=False,
        ),
        stats=None,
    )


def _target_state(
    legal_history: list[HistoricalMatch],
    target: PreMatchState,
) -> tuple[MatchProfilePair, FoundationalSnapshot]:
    replay = [*legal_history, _target_sentinel(target)]
    pairs = walk_forward_player_profiles(replay, exclude_retirements=False)
    foundational = walk_forward_foundational_features(replay, exclude_retirements=False)
    pair_matches = [item for item in pairs if item.match_id == target.match_id]
    foundational_matches = [item for item in foundational if item.match_id == target.match_id]
    if len(pair_matches) != 1 or len(foundational_matches) != 1:
        raise ValueError("prospective state replay did not emit exactly one target state")
    return pair_matches[0], foundational_matches[0]


def build_prospective_state_artifact(
    *,
    history: list[HistoricalMatch],
    target: PreMatchState,
    history_source_id: str,
    history_source_sha256: str,
    profile_artifact: ProfileProductionArtifact,
    core_artifact: CoreProductionArtifact,
) -> ProspectiveStateArtifact:
    if target.tour != _TOUR:
        raise ValueError("PATTERN-CONFIRM-001 prospective state is ATP only")
    if not str(history_source_id).strip():
        raise ValueError("history_source_id must be non-empty")
    source_sha = _sha_field(history_source_sha256, field="history_source_sha256")
    if any(match.match_id == target.match_id for match in history):
        raise ValueError("target match_id already exists in prospective state history")
    legal = _legal_history(history, target.event_date)
    pair, foundational = _target_state(legal, target)
    profile_gap = profile_gap_from_artifact(pair, profile_artifact)
    core_probability = core_probability_from_artifact(foundational, core_artifact)
    if not math.isfinite(profile_gap):
        raise ValueError("internally generated Profile Gap is not finite")
    if not math.isfinite(core_probability) or not 0.0 < core_probability < 1.0:
        raise ValueError("internally generated Core probability is outside (0, 1)")

    unsigned: dict[str, object] = {
        "version": _VERSION,
        "tour": _TOUR,
        "match_id": target.match_id,
        "event_date": target.event_date.isoformat(),
        "history_source_id": str(history_source_id).strip(),
        "history_source_sha256": source_sha,
        "history_n": len(legal),
        "history_rows_sha256": _history_rows_hash(legal),
        "profile_model_sha256": profile_artifact.artifact_sha256,
        "core_model_sha256": core_artifact.artifact_sha256,
        "target_pre_match": _pre_match_as_dict(target),
        "profile_pair": _profile_pair_as_dict(pair),
        "foundational_snapshot": _foundational_as_dict(foundational),
        "profile_gap": profile_gap,
        "core_probability_a": core_probability,
    }
    return ProspectiveStateArtifact(**unsigned, artifact_sha256=_self_hash(unsigned))


def prospective_state_as_dict(artifact: ProspectiveStateArtifact) -> dict[str, object]:
    return asdict(artifact)


def verify_prospective_state_artifact(
    payload: dict[str, object],
    *,
    profile_artifact: ProfileProductionArtifact,
    core_artifact: CoreProductionArtifact,
) -> ProspectiveStateArtifact:
    stored = str(payload.get("artifact_sha256", ""))
    if not stored or stored != _self_hash(payload):
        raise ValueError("prospective state artifact digest mismatch")
    artifact = ProspectiveStateArtifact(**payload)
    if artifact.version != _VERSION or artifact.tour != _TOUR:
        raise ValueError("unexpected prospective state contract")
    _sha_field(artifact.history_source_sha256, field="history_source_sha256")
    _sha_field(artifact.history_rows_sha256, field="history_rows_sha256")
    if artifact.profile_model_sha256 != profile_artifact.artifact_sha256:
        raise ValueError("prospective state Profile artifact mismatch")
    if artifact.core_model_sha256 != core_artifact.artifact_sha256:
        raise ValueError("prospective state Core artifact mismatch")
    if not isinstance(artifact.target_pre_match, dict):
        raise ValueError("target_pre_match must be an object")
    if not isinstance(artifact.profile_pair, dict):
        raise ValueError("profile_pair must be an object")
    if not isinstance(artifact.foundational_snapshot, dict):
        raise ValueError("foundational_snapshot must be an object")
    target = _pre_match_from_dict(artifact.target_pre_match)
    pair = _profile_pair_from_dict(artifact.profile_pair)
    foundational = _foundational_from_dict(artifact.foundational_snapshot)
    if target.match_id != artifact.match_id or pair.match_id != artifact.match_id:
        raise ValueError("prospective state match identity mismatch")
    if foundational.match_id != artifact.match_id:
        raise ValueError("prospective foundational match identity mismatch")
    if target.event_date.isoformat() != artifact.event_date:
        raise ValueError("prospective target event date mismatch")
    if pair.event_date != target.event_date or foundational.event_date != target.event_date:
        raise ValueError("prospective state target dates do not agree")
    if (
        pair.player_a.player_id != target.player_a_id
        or pair.player_b.player_id != target.player_b_id
    ):
        raise ValueError("prospective Profile player orientation mismatch")

    expected_profile = profile_gap_from_artifact(pair, profile_artifact)
    expected_core = core_probability_from_artifact(foundational, core_artifact)
    if artifact.profile_gap != expected_profile:
        raise ValueError("stored Profile Gap does not reproduce from sealed state")
    if artifact.core_probability_a != expected_core:
        raise ValueError("stored Core probability does not reproduce from sealed state")
    return artifact
