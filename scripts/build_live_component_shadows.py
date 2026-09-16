from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import tennis_genome.research_workbench.component_challengers as component_module
from tennis_genome.research_workbench import ImmutableResearchRegistry
from tennis_genome.research_workbench.component_challengers import (
    build_component_shadow_bundle,
    canonical_record_json,
)

_REGISTRATION_EPOCH = datetime(2026, 9, 16, 18, 13, 15, tzinfo=UTC)


def _load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _implementation_sha256() -> str:
    path = Path(component_module.__file__ or "")
    if not path.is_file():
        raise RuntimeError("unable to locate component challenger implementation")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_exact(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")


def build(
    *,
    prediction_dossier_path: Path,
    matchup_input_path: Path,
    target_resolution_path: Path,
    output_dir: Path,
    created_at: datetime,
) -> dict[str, object]:
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    implementation_sha = _implementation_sha256()
    bundle = build_component_shadow_bundle(
        prediction_dossier=_load_object(prediction_dossier_path),
        matchup_input=_load_object(matchup_input_path),
        target_resolution=_load_object(target_resolution_path),
        created_at=created_at,
        implementation_sha256=implementation_sha,
        registered_at=_REGISTRATION_EPOCH,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    registry = ImmutableResearchRegistry(output_dir / "registry")
    registry.register("snapshots", bundle.snapshot)
    for registration in bundle.registrations:
        registry.register("challenger-registrations", registration)
    for prediction in bundle.predictions:
        registry.register("shadow-predictions", prediction)

    _write_exact(output_dir / "snapshot.json", canonical_record_json(bundle.snapshot))
    registration_dir = output_dir / "registrations"
    prediction_dir = output_dir / "predictions"
    anchor_requests: list[dict[str, str]] = []
    for registration in bundle.registrations:
        _write_exact(
            registration_dir / f"{registration.challenger_id}.json",
            canonical_record_json(registration),
        )
    for prediction in bundle.predictions:
        canonical = canonical_record_json(prediction)
        _write_exact(
            prediction_dir / f"{prediction.output.challenger_id}.json",
            canonical,
        )
        anchor_requests.append(
            {
                "shadow_prediction_id": prediction.shadow_prediction_id,
                "shadow_prediction_sha256": prediction.semantic_sha256,
                "shadow_record_json": canonical,
            }
        )

    manifest = {
        "schema_version": "tennis-genome-live-component-shadow-manifest-v1",
        "created_at": created_at.isoformat(),
        "implementation_sha256": implementation_sha,
        "bundle_sha256": bundle.semantic_sha256,
        "snapshot_sha256": bundle.snapshot.semantic_sha256,
        "registration_sha256": {
            item.challenger_id: item.semantic_sha256 for item in bundle.registrations
        },
        "shadow_prediction_sha256": {
            item.output.challenger_id: item.semantic_sha256 for item in bundle.predictions
        },
        "anchor_requests": anchor_requests,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build immutable component shadow predictions from one champion artifact"
    )
    parser.add_argument("--prediction-dossier", type=Path, required=True)
    parser.add_argument("--matchup-input", type=Path, required=True)
    parser.add_argument("--target-resolution", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--created-at",
        help="timezone-aware ISO timestamp; defaults to current UTC",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    created_at = (
        datetime.fromisoformat(args.created_at)
        if args.created_at
        else datetime.now(UTC)
    )
    manifest = build(
        prediction_dossier_path=args.prediction_dossier,
        matchup_input_path=args.matchup_input,
        target_resolution_path=args.target_resolution,
        output_dir=args.output_dir,
        created_at=created_at,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
