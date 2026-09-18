from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from tennis_genome.research_workbench.api_tennis_prospective_evidence import (
    capture_api_tennis_slate_extension,
)


def _load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def build(
    *,
    history_wta_path: Path,
    slate_resolution_path: Path,
    history_artifact_id: int,
    output_dir: Path,
    captured_at: datetime,
) -> dict[str, object]:
    slate = _load_object(slate_resolution_path)
    targets = slate.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError("slate resolution must contain at least one target")
    if any(not isinstance(item, dict) for item in targets):
        raise ValueError("slate targets must all be JSON objects")

    extension_raw, capture = capture_api_tennis_slate_extension(
        history_raw_wta=history_wta_path.read_bytes(),
        history_artifact_id=history_artifact_id,
        target_resolutions=[dict(item) for item in targets],
        api_key=os.environ.get("API_TENNIS_API", ""),
        captured_at=captured_at,
    )

    output_dir.mkdir(parents=True, exist_ok=False)
    raw_path = output_dir / "raw-wta-extension.json"
    capture_path = output_dir / "capture-record.json"
    manifest_path = output_dir / "manifest.json"
    raw_path.write_bytes(extension_raw)
    capture_path.write_text(
        json.dumps(capture.canonical_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "tennis-genome-api-tennis-slate-extension-manifest-v1",
        "history_artifact_id": history_artifact_id,
        "provider_request_count": capture.provider_request_count,
        "query_date_start": capture.query_date_start.isoformat(),
        "query_date_stop": capture.query_date_stop.isoformat(),
        "base_history_raw_sha256": capture.base_history_raw_sha256,
        "extension_raw_sha256": capture.extension_raw_sha256,
        "captured_at": capture.captured_at.isoformat(),
        "target_event_ids": list(capture.target_event_ids),
        "prestart_target_event_ids": list(capture.prestart_target_event_ids),
        "late_target_event_ids": list(capture.late_target_event_ids),
        "market_blind": capture.market_blind,
        "target_outcome_consumed": False,
        "shared_capture_scope": "SLATE",
        "capture_record_sha256": capture.semantic_sha256,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture one API-Tennis WTA extension for a complete Forward-004 slate"
    )
    parser.add_argument("--history-wta", type=Path, required=True)
    parser.add_argument("--slate-resolution", type=Path, required=True)
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
        history_wta_path=args.history_wta,
        slate_resolution_path=args.slate_resolution,
        history_artifact_id=args.history_artifact_id,
        output_dir=args.output_dir,
        captured_at=captured_at,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
