from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

_VERSION = "pattern-confirm-sportradar-crosswalk-v1"


@dataclass(frozen=True)
class CrosswalkEntry:
    sportradar_competitor_id: str
    canonical_player_id: str


@dataclass(frozen=True)
class SportradarCanonicalCrosswalk:
    version: str
    entries: tuple[CrosswalkEntry, ...]
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


def seal_crosswalk(entries: dict[str, str]) -> SportradarCanonicalCrosswalk:
    normalized: list[CrosswalkEntry] = []
    canonical_ids: set[str] = set()
    for sportradar_id, canonical_id in sorted(entries.items()):
        sportradar_id = str(sportradar_id).strip()
        canonical_id = str(canonical_id).strip()
        if not sportradar_id or not canonical_id:
            raise ValueError("crosswalk IDs must be non-empty")
        if canonical_id in canonical_ids:
            raise ValueError("crosswalk canonical player IDs must be one-to-one")
        canonical_ids.add(canonical_id)
        normalized.append(CrosswalkEntry(sportradar_id, canonical_id))
    if not normalized:
        raise ValueError("crosswalk cannot be empty")
    unsigned: dict[str, object] = {
        "version": _VERSION,
        "entries": [asdict(entry) for entry in normalized],
    }
    return SportradarCanonicalCrosswalk(
        version=_VERSION,
        entries=tuple(normalized),
        artifact_sha256=_self_hash(unsigned),
    )


def crosswalk_as_dict(crosswalk: SportradarCanonicalCrosswalk) -> dict[str, object]:
    return {
        "version": crosswalk.version,
        "entries": [asdict(entry) for entry in crosswalk.entries],
        "artifact_sha256": crosswalk.artifact_sha256,
    }


def verify_crosswalk(payload: dict[str, object]) -> SportradarCanonicalCrosswalk:
    if str(payload.get("artifact_sha256", "")) != _self_hash(payload):
        raise ValueError("Sportradar canonical crosswalk digest mismatch")
    if payload.get("version") != _VERSION:
        raise ValueError("unexpected Sportradar canonical crosswalk version")
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        raise ValueError("crosswalk entries must be an array")
    mapping: dict[str, str] = {}
    for raw in raw_entries:
        if not isinstance(raw, dict):
            raise ValueError("crosswalk entry must be an object")
        sportradar_id = str(raw.get("sportradar_competitor_id", "")).strip()
        canonical_id = str(raw.get("canonical_player_id", "")).strip()
        if not sportradar_id or not canonical_id:
            raise ValueError("crosswalk IDs must be non-empty")
        if sportradar_id in mapping:
            raise ValueError("crosswalk Sportradar IDs must be unique")
        mapping[sportradar_id] = canonical_id
    rebuilt = seal_crosswalk(mapping)
    if rebuilt.artifact_sha256 != payload["artifact_sha256"]:
        raise ValueError("crosswalk is not in canonical deterministic order")
    return rebuilt


def crosswalk_mapping(crosswalk: SportradarCanonicalCrosswalk) -> dict[str, str]:
    return {
        entry.sportradar_competitor_id: entry.canonical_player_id
        for entry in crosswalk.entries
    }
