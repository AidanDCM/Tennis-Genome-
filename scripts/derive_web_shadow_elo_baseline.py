from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

_SCHEMA = "tennis-genome-web-shadow-baseline-v1"
_RECORD_TYPE = "WEB_SHADOW_BASELINE"
_BASELINE_NAME = "overall_elo_v1"


def _canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON must contain an object: {path}")
    return payload


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def derive_elo_baseline(
    *,
    matchup_input_path: Path,
    local_input_manifest_path: Path,
    prediction_path: Path,
    slate_id: str,
    artifact_id: int,
    artifact_sha256: str,
    output_path: Path,
) -> dict[str, Any]:
    matchup = _load_json(matchup_input_path)
    manifest = _load_json(local_input_manifest_path)
    prediction = _load_json(prediction_path)

    if prediction.get("record_type") != "WEB_SHADOW_PREDICTION":
        raise ValueError("baseline source must be a Web Shadow prediction")
    if prediction.get("production_eligible") is not False:
        raise ValueError("baseline source prediction must remain non-production")
    if manifest.get("production_eligible") is not False:
        raise ValueError("baseline source manifest must remain non-production")

    expected_input_sha = str(manifest.get("matchup_input_sha256", "")).strip()
    observed_input_sha = _sha256_file(matchup_input_path)
    if not expected_input_sha or expected_input_sha != observed_input_sha:
        raise ValueError("matchup input SHA differs from local input manifest")

    fixture = prediction.get("fixture")
    if not isinstance(fixture, dict):
        raise ValueError("baseline source prediction lacks fixture")
    match_id = str(fixture.get("match_id", "")).strip()
    if not match_id or match_id != matchup.get("match_id"):
        raise ValueError("baseline source match identities differ")

    player_a_id = str(prediction.get("player_a_id", "")).strip()
    player_b_id = str(prediction.get("player_b_id", "")).strip()
    if player_a_id != matchup.get("player_a_id"):
        raise ValueError("baseline player A identity differs from matchup input")
    if player_b_id != matchup.get("player_b_id"):
        raise ValueError("baseline player B identity differs from matchup input")

    foundational = matchup.get("foundational")
    if not isinstance(foundational, dict):
        raise ValueError("matchup input lacks foundational state")
    elo_logit = float(foundational["elo_logit"])
    if not math.isfinite(elo_logit):
        raise ValueError("Elo logit must be finite")

    p_player_a = 1.0 / (1.0 + math.exp(-elo_logit))
    p_player_b = 1.0 - p_player_a
    player_a = str(fixture.get("player_a", "")).strip()
    player_b = str(fixture.get("player_b", "")).strip()
    if not player_a or not player_b or player_a == player_b:
        raise ValueError("baseline fixture player names are invalid")

    selected_player = player_a if p_player_a >= 0.5 else player_b
    artifact_digest = artifact_sha256.strip().lower()
    if len(artifact_digest) != 64:
        raise ValueError("artifact SHA-256 must contain 64 hex characters")
    try:
        int(artifact_digest, 16)
    except ValueError as exc:
        raise ValueError("artifact SHA-256 must be hexadecimal") from exc
    if artifact_id <= 0:
        raise ValueError("artifact_id must be positive")
    if not slate_id.strip():
        raise ValueError("slate_id must be non-empty")

    record: dict[str, Any] = {
        "schema_version": _SCHEMA,
        "record_type": _RECORD_TYPE,
        "baseline_name": _BASELINE_NAME,
        "slate_id": slate_id,
        "match_id": match_id,
        "prediction_record_sha256": str(prediction.get("record_sha256", "")),
        "artifact_id": artifact_id,
        "artifact_sha256": artifact_digest,
        "matchup_input_sha256": observed_input_sha,
        "elo_logit": elo_logit,
        "p_player_a": p_player_a,
        "p_player_b": p_player_b,
        "selected_player": selected_player,
        "production_eligible": False,
    }
    record["record_sha256"] = _canonical_sha256(record)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return record


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Derive a frozen Elo-only benchmark from a Web Shadow matchup input"
    )
    parser.add_argument("--matchup-input", required=True, type=Path)
    parser.add_argument("--local-input-manifest", required=True, type=Path)
    parser.add_argument("--prediction", required=True, type=Path)
    parser.add_argument("--slate-id", required=True)
    parser.add_argument("--artifact-id", required=True, type=int)
    parser.add_argument("--artifact-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    record = derive_elo_baseline(
        matchup_input_path=args.matchup_input,
        local_input_manifest_path=args.local_input_manifest,
        prediction_path=args.prediction,
        slate_id=args.slate_id,
        artifact_id=args.artifact_id,
        artifact_sha256=args.artifact_sha256,
        output_path=args.output,
    )
    print(json.dumps(record, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
