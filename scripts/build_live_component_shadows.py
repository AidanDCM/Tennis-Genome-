from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import tennis_genome.research_workbench.api_tennis_prospective_shadow as api_tennis_module
import tennis_genome.research_workbench.component_challengers as component_module
from tennis_genome.research_workbench import ImmutableResearchRegistry
from tennis_genome.research_workbench.api_tennis_prospective_shadow import (
    ApiTennisChampionCrosswalk,
    ApiTennisProspectiveStateEvidence,
    build_api_tennis_deep_history_prospective_shadow_bundle,
    build_api_tennis_prospective_shadow_bundle,
)
from tennis_genome.research_workbench.challenger import validate_shadow_prediction_set
from tennis_genome.research_workbench.component_challengers import (
    build_component_shadow_bundle,
    canonical_record_json,
)

_REGISTRATION_EPOCH = datetime(2026, 9, 16, 18, 13, 15, tzinfo=UTC)
_API_TENNIS_REGISTRATION_EPOCH = datetime(2026, 9, 18, 12, 22, 5, tzinfo=UTC)
_API_TENNIS_DEEP500_REGISTRATION_EPOCH = datetime(2026, 9, 18, 16, 17, 30, tzinfo=UTC)


def _load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _module_sha256(module_file: str | None) -> str:
    path = Path(module_file or "")
    if not path.is_file():
        raise RuntimeError("unable to locate challenger implementation")
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
    api_tennis_evidence_path: Path | None = None,
    api_tennis_crosswalk_path: Path | None = None,
) -> dict[str, object]:
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    if (api_tennis_evidence_path is None) != (api_tennis_crosswalk_path is None):
        raise ValueError("API-Tennis evidence and crosswalk must be supplied together")

    component_implementation_sha = _module_sha256(component_module.__file__)
    component_bundle = build_component_shadow_bundle(
        prediction_dossier=_load_object(prediction_dossier_path),
        matchup_input=_load_object(matchup_input_path),
        target_resolution=_load_object(target_resolution_path),
        created_at=created_at,
        implementation_sha256=component_implementation_sha,
        registered_at=_REGISTRATION_EPOCH,
    )

    registrations = list(component_bundle.registrations)
    predictions = list(component_bundle.predictions)
    supplemental_bundle = None
    deep_history_bundle = None
    api_tennis_implementation_sha: str | None = None
    if api_tennis_evidence_path is not None and api_tennis_crosswalk_path is not None:
        api_tennis_implementation_sha = _module_sha256(api_tennis_module.__file__)
        evidence = ApiTennisProspectiveStateEvidence.model_validate(
            _load_object(api_tennis_evidence_path)
        )
        crosswalk = ApiTennisChampionCrosswalk.model_validate(
            _load_object(api_tennis_crosswalk_path)
        )
        supplemental_bundle = build_api_tennis_prospective_shadow_bundle(
            snapshot=component_bundle.snapshot,
            evidence=evidence,
            crosswalk=crosswalk,
            created_at=created_at,
            implementation_sha256=api_tennis_implementation_sha,
            registered_at=_API_TENNIS_REGISTRATION_EPOCH,
        )
        registrations.append(supplemental_bundle.registration)
        if supplemental_bundle.prediction is not None:
            predictions.append(supplemental_bundle.prediction)

        if created_at >= _API_TENNIS_DEEP500_REGISTRATION_EPOCH:
            deep_history_bundle = build_api_tennis_deep_history_prospective_shadow_bundle(
                snapshot=component_bundle.snapshot,
                evidence=evidence,
                crosswalk=crosswalk,
                created_at=created_at,
                implementation_sha256=api_tennis_implementation_sha,
                registered_at=_API_TENNIS_DEEP500_REGISTRATION_EPOCH,
            )
            registrations.append(deep_history_bundle.registration)
            if deep_history_bundle.prediction is not None:
                predictions.append(deep_history_bundle.prediction)

    prediction_tuple = tuple(predictions)
    validate_shadow_prediction_set(prediction_tuple)

    output_dir.mkdir(parents=True, exist_ok=False)
    registry = ImmutableResearchRegistry(output_dir / "registry")
    registry.register("snapshots", component_bundle.snapshot)
    for registration in registrations:
        registry.register("challenger-registrations", registration)
    for prediction in prediction_tuple:
        registry.register("shadow-predictions", prediction)
    if supplemental_bundle is not None:
        registry.register(
            "api-tennis-prospective-shadow-bundles",
            supplemental_bundle,
        )
    if deep_history_bundle is not None:
        registry.register(
            "api-tennis-deep-history-shadow-bundles",
            deep_history_bundle,
        )

    _write_exact(
        output_dir / "snapshot.json",
        canonical_record_json(component_bundle.snapshot),
    )
    registration_dir = output_dir / "registrations"
    prediction_dir = output_dir / "predictions"
    anchor_requests: list[dict[str, str]] = []
    for registration in registrations:
        _write_exact(
            registration_dir / f"{registration.challenger_id}.json",
            canonical_record_json(registration),
        )
    for prediction in prediction_tuple:
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

    supplemental_payload: dict[str, object] | None = None
    if supplemental_bundle is not None:
        supplemental_dir = output_dir / "supplemental-api-tennis"
        _write_exact(
            supplemental_dir / "state-evidence.json",
            canonical_record_json(supplemental_bundle.evidence),
        )
        _write_exact(
            supplemental_dir / "crosswalk.json",
            canonical_record_json(supplemental_bundle.crosswalk),
        )
        _write_exact(
            supplemental_dir / "bundle.json",
            canonical_record_json(supplemental_bundle),
        )
        if deep_history_bundle is not None:
            _write_exact(
                supplemental_dir / "deep-history-bundle.json",
                canonical_record_json(deep_history_bundle),
            )
        supplemental_payload = {
            "bundle_sha256": supplemental_bundle.semantic_sha256,
            "evidence_sha256": supplemental_bundle.evidence.semantic_sha256,
            "crosswalk_sha256": supplemental_bundle.crosswalk.semantic_sha256,
            "registration_sha256": supplemental_bundle.registration.semantic_sha256,
            "prediction_sha256": (
                supplemental_bundle.prediction.semantic_sha256
                if supplemental_bundle.prediction is not None
                else None
            ),
            "abstained": supplemental_bundle.prediction is None,
            "deep_history_registered": deep_history_bundle is not None,
            "deep_history_bundle_sha256": (
                deep_history_bundle.semantic_sha256
                if deep_history_bundle is not None
                else None
            ),
            "deep_history_registration_sha256": (
                deep_history_bundle.registration.semantic_sha256
                if deep_history_bundle is not None
                else None
            ),
            "deep_history_prediction_sha256": (
                deep_history_bundle.prediction.semantic_sha256
                if (
                    deep_history_bundle is not None
                    and deep_history_bundle.prediction is not None
                )
                else None
            ),
            "deep_history_abstained": (
                deep_history_bundle.prediction is None
                if deep_history_bundle is not None
                else None
            ),
        }

    manifest = {
        "schema_version": "tennis-genome-live-component-shadow-manifest-v1",
        "created_at": created_at.isoformat(),
        "implementation_sha256": component_implementation_sha,
        "component_implementation_sha256": component_implementation_sha,
        "api_tennis_implementation_sha256": api_tennis_implementation_sha,
        "bundle_sha256": component_bundle.semantic_sha256,
        "snapshot_sha256": component_bundle.snapshot.semantic_sha256,
        "registration_count": len(registrations),
        "prediction_count": len(prediction_tuple),
        "registration_sha256": {
            item.challenger_id: item.semantic_sha256 for item in registrations
        },
        "shadow_prediction_sha256": {
            item.output.challenger_id: item.semantic_sha256 for item in prediction_tuple
        },
        "supplemental_api_tennis": supplemental_payload,
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
    parser.add_argument("--api-tennis-evidence", type=Path)
    parser.add_argument("--api-tennis-crosswalk", type=Path)
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
        api_tennis_evidence_path=args.api_tennis_evidence,
        api_tennis_crosswalk_path=args.api_tennis_crosswalk,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
