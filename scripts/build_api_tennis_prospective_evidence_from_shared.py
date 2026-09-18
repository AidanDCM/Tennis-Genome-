from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from tennis_genome.research_workbench.api_tennis_prospective_evidence import (
    build_api_tennis_prospective_evidence,
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
    shared_extension_path: Path,
    shared_capture_manifest_path: Path,
    champion_prediction_artifact_id: int,
    history_artifact_id: int,
    shared_extension_artifact_id: int,
    output_dir: Path,
) -> dict[str, object]:
    shared_manifest = _load_object(shared_capture_manifest_path)
    if (
        shared_manifest.get("schema_version")
        != "tennis-genome-api-tennis-slate-extension-manifest-v1"
    ):
        raise ValueError("unexpected shared API-Tennis slate manifest schema")
    if int(shared_manifest.get("history_artifact_id", 0)) != history_artifact_id:
        raise ValueError("shared capture history artifact ID mismatch")
    if shared_manifest.get("provider_request_count") != 1:
        raise ValueError("shared capture must originate from exactly one provider request")
    if shared_manifest.get("market_blind") is not True:
        raise ValueError("shared capture must be market blind")
    if shared_manifest.get("target_outcome_consumed") is not False:
        raise ValueError("shared capture must be target-outcome blind")

    target_resolution = _load_object(target_resolution_path)
    event_id = str(target_resolution.get("event_id", ""))
    prestart = shared_manifest.get("prestart_target_event_ids")
    if not isinstance(prestart, list) or event_id not in prestart:
        raise ValueError("target is not in shared capture pre-start population")

    captured_at = datetime.fromisoformat(str(shared_manifest.get("captured_at", "")))
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("shared capture timestamp must be timezone-aware")

    extension_raw = shared_extension_path.read_bytes()
    evidence, crosswalk, build_record = build_api_tennis_prospective_evidence(
        history_raw_wta=history_wta_path.read_bytes(),
        extension_raw_wta=extension_raw,
        champion_prediction_artifact_id=champion_prediction_artifact_id,
        history_artifact_id=history_artifact_id,
        prediction_dossier=_load_object(prediction_dossier_path),
        target_resolution=target_resolution,
        captured_at=captured_at,
    )

    if build_record.extension_raw_sha256 != shared_manifest.get("extension_raw_sha256"):
        raise ValueError("per-match build did not reproduce shared extension hash")
    if build_record.base_history_raw_sha256 != shared_manifest.get(
        "base_history_raw_sha256"
    ):
        raise ValueError("per-match build did not reproduce shared base-history hash")

    output_dir.mkdir(parents=True, exist_ok=False)
    _write_record(output_dir / "api-tennis-prospective-state.json", evidence)
    _write_record(output_dir / "api-tennis-champion-crosswalk.json", crosswalk)
    _write_record(output_dir / "build-record.json", build_record)
    manifest = {
        "schema_version": (
            "tennis-genome-api-tennis-prospective-evidence-shared-slate-manifest-v1"
        ),
        "champion_prediction_artifact_id": champion_prediction_artifact_id,
        "history_artifact_id": history_artifact_id,
        "shared_extension_artifact_id": shared_extension_artifact_id,
        "local_provider_request_count": 0,
        "source_capture_provider_request_count": 1,
        "shared_capture_scope": "SLATE",
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
        description=(
            "Build one target's API-Tennis WTA evidence from a shared retained slate capture"
        )
    )
    parser.add_argument("--prediction-dossier", type=Path, required=True)
    parser.add_argument("--target-resolution", type=Path, required=True)
    parser.add_argument("--history-wta", type=Path, required=True)
    parser.add_argument("--shared-extension", type=Path, required=True)
    parser.add_argument("--shared-capture-manifest", type=Path, required=True)
    parser.add_argument("--champion-prediction-artifact-id", type=int, required=True)
    parser.add_argument("--history-artifact-id", type=int, required=True)
    parser.add_argument("--shared-extension-artifact-id", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = build(
        prediction_dossier_path=args.prediction_dossier,
        target_resolution_path=args.target_resolution,
        history_wta_path=args.history_wta,
        shared_extension_path=args.shared_extension,
        shared_capture_manifest_path=args.shared_capture_manifest,
        champion_prediction_artifact_id=args.champion_prediction_artifact_id,
        history_artifact_id=args.history_artifact_id,
        shared_extension_artifact_id=args.shared_extension_artifact_id,
        output_dir=args.output_dir,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
