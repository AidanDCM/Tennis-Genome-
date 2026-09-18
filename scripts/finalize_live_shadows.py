from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from tennis_genome.evaluation.validation import (
    ValidationObservation,
    build_validation_report,
)
from tennis_genome.research_workbench import (
    CommonPreMatchSnapshot,
    ImmutableResearchRegistry,
    ShadowPredictionRecord,
)
from tennis_genome.research_workbench.component_challengers import canonical_record_json
from tennis_genome.research_workbench.shadow_finalize import (
    binding_from_verified_dossier,
    finalize_shadow_match,
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _load_shadow_predictions(shadow_root: Path) -> tuple[ShadowPredictionRecord, ...]:
    paths = sorted((shadow_root / "predictions").glob("*.json"))
    if not paths:
        raise ValueError("shadow artifact contains no prediction records")
    return tuple(
        ShadowPredictionRecord.model_validate_json(path.read_text(encoding="utf-8"))
        for path in paths
    )


def _verify_retained_anchor_receipts(
    *, shadow_root: Path, predictions: tuple[ShadowPredictionRecord, ...]
) -> tuple[int, ...]:
    receipts = sorted((shadow_root / "anchors").glob("*.comment.json.receipt.json"))
    if len(receipts) != len(predictions):
        raise ValueError("retained shadow anchor receipt count differs from prediction count")
    expected = {
        prediction.shadow_prediction_id: prediction for prediction in predictions
    }
    if len(expected) != len(predictions):
        raise ValueError("duplicate shadow prediction IDs are forbidden")
    comment_ids: list[int] = []
    seen: set[str] = set()
    for path in receipts:
        receipt = _load_json_object(path)
        prediction_id = str(receipt["shadow_prediction_id"])
        if prediction_id in seen:
            raise ValueError("duplicate retained shadow anchor receipt")
        seen.add(prediction_id)
        prediction = expected.get(prediction_id)
        if prediction is None:
            raise ValueError("retained anchor receipt references unknown shadow prediction")
        if str(receipt["shadow_prediction_sha256"]) != prediction.semantic_sha256:
            raise ValueError("retained shadow anchor prediction hash mismatch")
        if str(receipt["snapshot_sha256"]) != prediction.snapshot_sha256:
            raise ValueError("retained shadow anchor snapshot hash mismatch")
        if str(receipt["registration_sha256"]) != prediction.registration_sha256:
            raise ValueError("retained shadow anchor registration hash mismatch")
        if str(receipt["scheduled_start"]) != prediction.scheduled_start.isoformat().replace(
            "+00:00", "Z"
        ):
            raise ValueError("retained shadow anchor scheduled_start mismatch")
        comment_id = int(receipt["comment_id"])
        if comment_id <= 0:
            raise ValueError("retained shadow anchor comment ID must be positive")
        comment_ids.append(comment_id)
    if seen != set(expected):
        raise ValueError("not every shadow prediction has a retained anchor receipt")
    return tuple(sorted(comment_ids))


def build(
    *,
    shadow_root: Path,
    verified_settlement_dossier_path: Path,
    verified_settlement_artifact_id: int,
    source_shadow_artifact_id: int,
    output_dir: Path,
    settled_at: datetime,
) -> dict[str, object]:
    if settled_at.tzinfo is None or settled_at.utcoffset() is None:
        raise ValueError("settled_at must be timezone-aware")
    snapshot = CommonPreMatchSnapshot.model_validate_json(
        (shadow_root / "snapshot.json").read_text(encoding="utf-8")
    )
    predictions = _load_shadow_predictions(shadow_root)
    anchor_comment_ids = _verify_retained_anchor_receipts(
        shadow_root=shadow_root,
        predictions=predictions,
    )

    dossier_bytes = verified_settlement_dossier_path.read_bytes()
    dossier_sha = _sha256_bytes(dossier_bytes)
    sibling_sha = verified_settlement_dossier_path.with_suffix(".sha256")
    if sibling_sha.is_file():
        recorded = sibling_sha.read_text(encoding="utf-8").strip().split()[0]
        if recorded != dossier_sha:
            raise ValueError("verified settlement dossier SHA-256 does not match sidecar")
    dossier = json.loads(dossier_bytes)
    if not isinstance(dossier, dict):
        raise ValueError("verified settlement dossier must be one JSON object")
    binding = binding_from_verified_dossier(
        dossier=dossier,
        verified_settlement_artifact_id=verified_settlement_artifact_id,
        verified_settlement_dossier_sha256=dossier_sha,
    )

    # The immutable shadow anchors retain the source champion prediction artifact ID.
    retained_comment_files = sorted((shadow_root / "anchors").glob("*.comment.json"))
    source_prediction_artifact_ids: set[int] = set()
    for path in retained_comment_files:
        if path.name.endswith(".receipt.json"):
            continue
        comment = _load_json_object(path)
        body = str(comment.get("body", ""))
        marker = "```json\n"
        if marker not in body or not body.rstrip().endswith("```"):
            raise ValueError("retained shadow comment lacks canonical JSON fence")
        payload_text = body.split(marker, 1)[1].rsplit("\n```", 1)[0]
        payload = json.loads(payload_text)
        if not isinstance(payload, dict):
            raise ValueError("retained shadow comment payload must be an object")
        source_prediction_artifact_ids.add(int(payload["source_prediction_artifact_id"]))
    if source_prediction_artifact_ids != {binding.prediction_artifact_id}:
        raise ValueError(
            "shadow anchors and verified settlement do not bind one champion prediction artifact"
        )

    bundle = finalize_shadow_match(
        predictions=predictions,
        snapshot=snapshot,
        binding=binding,
        source_shadow_artifact_id=source_shadow_artifact_id,
        settled_at=settled_at,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    registry = ImmutableResearchRegistry(output_dir / "registry")
    for settlement in bundle.settlements:
        registry.register("shadow-settlements", settlement)
    for atlas in bundle.failure_atlas:
        registry.register("failure-atlas", atlas)
    registry.register("shadow-finalizations", bundle)

    settlement_dir = output_dir / "settlements"
    atlas_dir = output_dir / "failure-atlas"
    settlement_dir.mkdir(parents=True, exist_ok=True)
    atlas_dir.mkdir(parents=True, exist_ok=True)
    for settlement in bundle.settlements:
        challenger_id = next(
            prediction.output.challenger_id
            for prediction in predictions
            if prediction.shadow_prediction_id == settlement.shadow_prediction_id
        )
        (settlement_dir / f"{challenger_id}.json").write_text(
            canonical_record_json(settlement), encoding="utf-8"
        )
    for atlas in bundle.failure_atlas:
        (atlas_dir / f"{atlas.challenger_id}.json").write_text(
            canonical_record_json(atlas), encoding="utf-8"
        )
    (output_dir / "finalization-bundle.json").write_text(
        canonical_record_json(bundle), encoding="utf-8"
    )
    league_payload = [row.canonical_payload() for row in bundle.league_table]
    (output_dir / "league-table.json").write_text(
        json.dumps(league_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    validation_observation_dir = output_dir / "validation-observations"
    validation_report_dir = output_dir / "validation-reports"
    validation_observation_dir.mkdir(parents=True, exist_ok=True)
    validation_report_dir.mkdir(parents=True, exist_ok=True)
    validation_report_sha256: dict[str, str] = {}
    for atlas in bundle.failure_atlas:
        observation = ValidationObservation(
            model_id=atlas.challenger_id,
            match_id=atlas.match_id,
            event_date=snapshot.scheduled_start.date(),
            probability_a=atlas.p_player_a,
            outcome_a_won=atlas.outcome_player_a_won,
            component_probabilities=atlas.pre_match_component_probabilities,
            pre_match_diagnostics=atlas.pre_match_diagnostics,
            tags=atlas.deterministic_tags,
        )
        observation_payload = {
            "model_id": observation.model_id,
            "match_id": observation.match_id,
            "event_date": (
                None if observation.event_date is None else observation.event_date.isoformat()
            ),
            "probability_a": observation.probability_a,
            "outcome_a_won": observation.outcome_a_won,
            "component_probabilities": observation.component_probabilities,
            "pre_match_diagnostics": observation.pre_match_diagnostics,
            "tags": list(observation.tags),
        }
        observation_path = validation_observation_dir / f"{atlas.challenger_id}.json"
        observation_path.write_text(
            json.dumps(observation_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        validation_report = build_validation_report([observation], population_size=1)
        report_path = validation_report_dir / f"{atlas.challenger_id}.json"
        report_path.write_text(
            json.dumps(validation_report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        validation_report_sha256[atlas.challenger_id] = _sha256_bytes(
            report_path.read_bytes()
        )

    manifest = {
        "schema_version": "tennis-genome-shadow-settlement-manifest-v1",
        "settled_at": settled_at.isoformat(),
        "source_shadow_artifact_id": source_shadow_artifact_id,
        "source_prediction_artifact_id": binding.prediction_artifact_id,
        "verified_settlement_artifact_id": verified_settlement_artifact_id,
        "verified_settlement_dossier_sha256": dossier_sha,
        "match_id": binding.match_id,
        "winner_player_id": binding.winner_player_id,
        "snapshot_sha256": snapshot.semantic_sha256,
        "shadow_anchor_comment_ids": list(anchor_comment_ids),
        "finalization_bundle_sha256": bundle.semantic_sha256,
        "settlement_sha256": {
            prediction.output.challenger_id: settlement.semantic_sha256
            for prediction, settlement in zip(predictions, bundle.settlements, strict=True)
        },
        "failure_atlas_sha256": {
            atlas.challenger_id: atlas.semantic_sha256 for atlas in bundle.failure_atlas
        },
        "league_table": [row.canonical_payload() for row in bundle.league_table],
        "validation_report_sha256": validation_report_sha256,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalize trusted live challenger shadows from a verified settlement"
    )
    parser.add_argument("--shadow-root", type=Path, required=True)
    parser.add_argument("--verified-settlement-dossier", type=Path, required=True)
    parser.add_argument("--verified-settlement-artifact-id", type=int, required=True)
    parser.add_argument("--source-shadow-artifact-id", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--settled-at", help="timezone-aware ISO timestamp")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settled_at = (
        datetime.fromisoformat(args.settled_at)
        if args.settled_at
        else datetime.now(UTC)
    )
    manifest = build(
        shadow_root=args.shadow_root,
        verified_settlement_dossier_path=args.verified_settlement_dossier,
        verified_settlement_artifact_id=args.verified_settlement_artifact_id,
        source_shadow_artifact_id=args.source_shadow_artifact_id,
        output_dir=args.output_dir,
        settled_at=settled_at,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
