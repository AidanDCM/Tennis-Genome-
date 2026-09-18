from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from tennis_genome.evaluation.validation import (
    ValidationObservation,
    build_paired_model_comparison,
    build_validation_report,
)

IDENTITY_MODEL_ID = "TGE-SHADOW-IDENTITY-V1"


def _load_observation(path: Path) -> ValidationObservation:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain one observation object")
    event_date_raw = payload.get("event_date")
    return ValidationObservation(
        model_id=str(payload["model_id"]),
        match_id=str(payload["match_id"]),
        event_date=(
            None if event_date_raw in {None, ""} else date.fromisoformat(str(event_date_raw))
        ),
        probability_a=float(payload["probability_a"]),
        outcome_a_won=bool(payload["outcome_a_won"]),
        component_probabilities={
            str(key): float(value)
            for key, value in dict(payload.get("component_probabilities", {})).items()
        },
        pre_match_diagnostics=dict(payload.get("pre_match_diagnostics", {})),
        tags=tuple(str(value) for value in payload.get("tags", [])),
    )


def aggregate(*, settlement_root: Path, output_dir: Path) -> dict[str, object]:
    paths = sorted(settlement_root.rglob("validation-observations/*.json"))
    if not paths:
        raise ValueError("no forward validation observations were found")

    by_model: defaultdict[str, list[ValidationObservation]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for path in paths:
        observation = _load_observation(path)
        key = (observation.model_id, observation.match_id)
        if key in seen:
            raise ValueError(
                f"duplicate forward validation observation for {observation.model_id} "
                f"{observation.match_id}"
            )
        seen.add(key)
        by_model[observation.model_id].append(observation)

    identity_rows = by_model.get(IDENTITY_MODEL_ID)
    if not identity_rows:
        raise ValueError("forward validation aggregate requires identity/champion observations")
    identity_by_match = {row.match_id: row for row in identity_rows}

    output_dir.mkdir(parents=True, exist_ok=False)
    report_dir = output_dir / "reports"
    comparison_dir = output_dir / "paired-comparisons"
    report_dir.mkdir()
    comparison_dir.mkdir()

    report_sha256: dict[str, str] = {}
    comparison_sha256: dict[str, str] = {}
    reports: dict[str, dict[str, object]] = {}
    for model_id, rows in sorted(by_model.items()):
        report = build_validation_report(
            rows,
            population_size=len(identity_rows),
        )
        reports[model_id] = report
        path = report_dir / f"{model_id}.json"
        path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report_sha256[model_id] = hashlib.sha256(path.read_bytes()).hexdigest()

        if model_id == IDENTITY_MODEL_ID:
            continue
        paired_identity: list[ValidationObservation] = []
        for row in rows:
            identity = identity_by_match.get(row.match_id)
            if identity is None:
                raise ValueError(
                    f"challenger {model_id} match {row.match_id} lacks identity control"
                )
            paired_identity.append(identity)
        comparison = build_paired_model_comparison(paired_identity, rows)
        compare_path = comparison_dir / f"{model_id}-vs-{IDENTITY_MODEL_ID}.json"
        compare_path.write_text(
            json.dumps(comparison, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        comparison_sha256[model_id] = hashlib.sha256(compare_path.read_bytes()).hexdigest()

    manifest: dict[str, object] = {
        "schema_version": "tennis-genome-forward-validation-aggregate-v1",
        "identity_model_id": IDENTITY_MODEL_ID,
        "population_match_count": len(identity_rows),
        "model_count": len(by_model),
        "model_prediction_counts": {
            model_id: len(rows) for model_id, rows in sorted(by_model.items())
        },
        "model_coverage": {
            model_id: len(rows) / len(identity_rows)
            for model_id, rows in sorted(by_model.items())
        },
        "report_sha256": report_sha256,
        "paired_comparison_sha256": comparison_sha256,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "population_match_count": manifest["population_match_count"],
                "model_prediction_counts": manifest["model_prediction_counts"],
                "model_coverage": manifest["model_coverage"],
                "identity_overall": reports[IDENTITY_MODEL_ID]["overall"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate settled forward Champion/challenger validation metrics"
    )
    parser.add_argument("--settlement-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = aggregate(
        settlement_root=args.settlement_root,
        output_dir=args.output_dir,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
