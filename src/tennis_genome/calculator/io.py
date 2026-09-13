from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from tennis_genome.features.foundational import FoundationalSnapshot
from tennis_genome.profiles.state import MatchProfilePair, PlayerProfileSnapshot
from tennis_genome.ratings.serve_return import ServeReturnSnapshot

from .types import MatchupInput


def _datetime(value: object, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed


def _date(value: object, *, field: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date") from exc


def _foundational(payload: object) -> FoundationalSnapshot:
    if not isinstance(payload, dict):
        raise ValueError("foundational must be an object")
    normalized = dict(payload)
    normalized["event_date"] = _date(
        normalized.get("event_date"),
        field="foundational.event_date",
    )
    return FoundationalSnapshot(**normalized)


def _player_profile(payload: object, *, field: str) -> PlayerProfileSnapshot:
    if not isinstance(payload, dict):
        raise ValueError(f"{field} must be an object")
    normalized = dict(payload)
    normalized["valid_from"] = _date(
        normalized.get("valid_from"),
        field=f"{field}.valid_from",
    )
    valid_until = normalized.get("valid_until")
    normalized["valid_until"] = (
        None
        if valid_until is None
        else _date(valid_until, field=f"{field}.valid_until")
    )
    return PlayerProfileSnapshot(**normalized)


def _profile_pair(payload: object) -> MatchProfilePair:
    if not isinstance(payload, dict):
        raise ValueError("profile_pair must be an object")
    return MatchProfilePair(
        match_id=str(payload.get("match_id", "")),
        event_date=_date(payload.get("event_date"), field="profile_pair.event_date"),
        player_a=_player_profile(payload.get("player_a"), field="profile_pair.player_a"),
        player_b=_player_profile(payload.get("player_b"), field="profile_pair.player_b"),
    )


def _serve_return(payload: object) -> ServeReturnSnapshot:
    if not isinstance(payload, dict):
        raise ValueError("serve_return must be an object")
    normalized = dict(payload)
    normalized["event_date"] = _date(
        normalized.get("event_date"),
        field="serve_return.event_date",
    )
    return ServeReturnSnapshot(**normalized)


def matchup_input_from_dict(payload: dict[str, object]) -> MatchupInput:
    tour = str(payload.get("tour", ""))
    profile_payload = payload.get("profile_pair")
    serve_payload = payload.get("serve_return")
    source_hashes = payload.get("source_manifest_hashes")
    if not isinstance(source_hashes, list):
        raise ValueError("source_manifest_hashes must be an array")
    return MatchupInput(
        prediction_id=str(payload.get("prediction_id", "")),
        match_id=str(payload.get("match_id", "")),
        tour=tour,
        player_a_id=str(payload.get("player_a_id", "")),
        player_b_id=str(payload.get("player_b_id", "")),
        created_at=_datetime(payload.get("created_at"), field="created_at"),
        prediction_cutoff_at=_datetime(
            payload.get("prediction_cutoff_at"),
            field="prediction_cutoff_at",
        ),
        foundational=_foundational(payload.get("foundational")),
        source_manifest_hashes=tuple(str(value) for value in source_hashes),
        best_of=int(payload.get("best_of", 3)),
        profile_pair=None if profile_payload is None else _profile_pair(profile_payload),
        serve_return=None if serve_payload is None else _serve_return(serve_payload),
    )


def load_matchup_input(path: Path) -> MatchupInput:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("matchup input JSON must contain an object")
    return matchup_input_from_dict(payload)
