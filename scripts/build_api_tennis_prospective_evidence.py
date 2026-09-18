from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from tennis_genome.research_workbench.api_tennis_prospective_evidence import (
    capture_api_tennis_prospective_evidence,
)


def _load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _write_record(path: Path, record: object) -> None:
    payload = record.canonical_payload()  # type: ignore[attr-defined]
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build(
    *,
    prediction_dossier_path: Path,
    target_resolution_path: Path,
    history_wta_path: Path,
    champion_prediction_artifact_id: int,
    history_artifact_id: int,
    output_dir: Path,
    captured_at: datetime,
) -> dict[str, object]:
    extension_raw, evidence, crosswalk, build_record = (
        capture_api_tennis_prospective_evidence(
            history_raw_wta=history_wta_path.read_bytes(),
            champion_prediction_artifact_id=champion_prediction_artifact_id,
            history_artifact_id=history_artifact_id,
            prediction_dossier=_load_object(prediction_dossier_path),
            target_resolution=_load_object(target_resolution_path),
            api_key=os.environ.get("API_TENNIS_API", ""),
            captured_at=captured_at,
        )
    )

    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "raw-wta-extension.json").write_bytes(extension_raw)
    _write_record(output_dir / "api-tennis-prospective-state.json", evidence)
    _write_record(output_dir / "api-tennis-champion-crosswalk.json", crosswalk)
    _write_record(output_dir / "build-record.json", build_record)
    manifest = {
        "schema_version": "tennis-genome-api-tennis-prospective-evidence-manifest-v1",
        "champion_prediction_artifact_id": champion_prediction_artifact_id,
        "history_artifact_id": history_artifact_id,
        "provider_request_count": 1,
        "query_date_start": build_record.query_date_start.isoformat(),
        "query_date_stop": build_record.query_date_stop.isoformat(),
        "base_history_raw_sha256": build_record.base_history_raw_sha256,
        "extension_raw_sha256": build_record.extension_raw_sha256,
        "state_source_sha256": build_record.state_source_sha256,
        "target_fixture_sha256": build_record.target_fixture_sha256,
        "target_event_key": build_record.target_event_key,
        "target_event_date": build_record.target_event_date.isoformat(),
        "orientation": build_record.orientation,
        "evidence_sha256": evidence.semantic_sha256,
        "crosswalk_sha256": crosswalk.semantic_sha256,
        "build_record_sha256": build_record.semantic_sha256,
        "captured_at": captured_at.isoformat(),
        "market_blind": True,
        "target_outcome_consumed": False,
        "same_day_history_consumed": False,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture one-request pre-match API-Tennis WTA shadow evidence"
    )
    parser.add_argument("--prediction-dossier", type=Path, required=True)
    parser.add_argument("--target-resolution", type=Path, required=True)
    parser.add_argument("--history-wta", type=Path, required=True)
    parser.add_argument("--champion-prediction-artifact-id", type=int, required=True)
    parser.add_argument("--history-artifact-id", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--captured-at", help="timezone-aware ISO timestamp")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    captured_at = (
        datetime.fromisoformat(args.captured_at)
        if args.captured_at
        else datetime.now(UTC)
    )
    manifest = build(
        prediction_dossier_path=args.prediction_dossier,
        target_resolution_path=args.target_resolution,
        history_wta_path=args.history_wta,
        champion_prediction_artifact_id=args.champion_prediction_artifact_id,
        history_artifact_id=args.history_artifact_id,
        output_dir=args.output_dir,
        captured_at=captured_at,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
