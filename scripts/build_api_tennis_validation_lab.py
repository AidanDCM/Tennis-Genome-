from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from tennis_genome.evaluation.validation import (
    ValidationObservation,
    build_paired_model_comparison,
    build_validation_report,
)
from tennis_genome.research_workbench.api_tennis_conservative_wta_shadow import (
    CHALLENGER_ID,
    MIN_PRIOR_POINTS_PER_PLAYER,
    shrink_probability_to_neutral,
)
from tennis_genome.research_workbench.api_tennis_dynamic_shadow import SHADOW_MODEL_ID


def _load_replay(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("replay.json must contain one object")
    scores = payload.get("scores")
    if not isinstance(scores, list) or any(not isinstance(row, dict) for row in scores):
        raise ValueError("replay scores must be an array of objects")
    return payload


def _history_tags(row: dict[str, Any]) -> tuple[str, ...]:
    history_a = int(row["prior_serve_points_a"]) + int(row["prior_return_points_a"])
    history_b = int(row["prior_serve_points_b"]) + int(row["prior_return_points_b"])
    minimum = min(history_a, history_b)
    tags: set[str] = set()
    if history_a > 0 and history_b > 0:
        tags.add("BOTH_PLAYERS_HISTORY")
    if minimum >= MIN_PRIOR_POINTS_PER_PLAYER:
        tags.add("CONSERVATIVE_ELIGIBLE")
    if minimum < 200:
        tags.add("MIN_HISTORY_LT_200")
    elif minimum < 500:
        tags.add("MIN_HISTORY_200_499")
    elif minimum < 1000:
        tags.add("MIN_HISTORY_500_999")
    else:
        tags.add("MIN_HISTORY_GE_1000")
    return tuple(sorted(tags))


def _raw_observation(row: dict[str, Any]) -> ValidationObservation:
    return ValidationObservation(
        model_id=SHADOW_MODEL_ID,
        match_id=f"api-tennis:{int(row['event_key'])}",
        event_date=date.fromisoformat(str(row["event_date"])),
        probability_a=float(row["probability_a_match"]),
        outcome_a_won=str(row["winner_side"]) == "A",
        pre_match_diagnostics={
            "prior_serve_points_a": int(row["prior_serve_points_a"]),
            "prior_serve_points_b": int(row["prior_serve_points_b"]),
            "prior_return_points_a": int(row["prior_return_points_a"]),
            "prior_return_points_b": int(row["prior_return_points_b"]),
            "any_history": bool(row["any_history"]),
            "both_players_history": bool(row["both_players_history"]),
        },
        tags=_history_tags(row),
    )


def _conservative_observation(row: dict[str, Any]) -> ValidationObservation:
    raw_probability = float(row["probability_a_match"])
    probability = shrink_probability_to_neutral(raw_probability)
    return ValidationObservation(
        model_id=CHALLENGER_ID,
        match_id=f"api-tennis:{int(row['event_key'])}",
        event_date=date.fromisoformat(str(row["event_date"])),
        probability_a=probability,
        outcome_a_won=str(row["winner_side"]) == "A",
        component_probabilities={
            "dynamic_serve_return_raw": raw_probability,
            "neutral_reference": 0.5,
        },
        pre_match_diagnostics={
            "prior_serve_points_a": int(row["prior_serve_points_a"]),
            "prior_serve_points_b": int(row["prior_serve_points_b"]),
            "prior_return_points_a": int(row["prior_return_points_a"]),
            "prior_return_points_b": int(row["prior_return_points_b"]),
            "history_threshold": MIN_PRIOR_POINTS_PER_PLAYER,
            "shrinkage_to_neutral": 0.80,
            "retained_raw_weight": 0.20,
            "development_derived_rule": True,
        },
        tags=_history_tags(row),
    )


def build(*, replay_path: Path, output_dir: Path) -> dict[str, object]:
    replay_bytes = replay_path.read_bytes()
    replay = _load_replay(replay_path)
    wta_rows = [
        dict(row)
        for row in replay["scores"]
        if str(row.get("tour")) == "WTA"
    ]
    if not wta_rows:
        raise ValueError("validation lab requires at least one admitted WTA replay score")

    raw_all = [_raw_observation(row) for row in wta_rows]
    eligible_rows = [
        row
        for row in wta_rows
        if (
            int(row["prior_serve_points_a"]) + int(row["prior_return_points_a"])
            >= MIN_PRIOR_POINTS_PER_PLAYER
            and int(row["prior_serve_points_b"]) + int(row["prior_return_points_b"])
            >= MIN_PRIOR_POINTS_PER_PLAYER
        )
    ]
    if not eligible_rows:
        raise ValueError("validation lab found no conservative-eligible WTA scores")

    raw_eligible = [_raw_observation(row) for row in eligible_rows]
    conservative = [_conservative_observation(row) for row in eligible_rows]
    population_size = len(wta_rows)

    reports = {
        "raw_dynamic_all_wta": build_validation_report(
            raw_all,
            population_size=population_size,
        ),
        "raw_dynamic_conservative_eligible": build_validation_report(
            raw_eligible,
            population_size=population_size,
        ),
        "conservative_wta": build_validation_report(
            conservative,
            population_size=population_size,
        ),
    }
    comparison = build_paired_model_comparison(raw_eligible, conservative)

    output_dir.mkdir(parents=True, exist_ok=False)
    reports_dir = output_dir / "reports"
    reports_dir.mkdir()
    for name, report in reports.items():
        (reports_dir / f"{name}.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    (output_dir / "paired-conservative-vs-raw.json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest: dict[str, object] = {
        "schema_version": "tennis-genome-api-tennis-validation-lab-v1",
        "source_replay_id": replay.get("replay_id"),
        "source_replay_file_sha256": hashlib.sha256(replay_bytes).hexdigest(),
        "wta_population_count": population_size,
        "conservative_eligible_count": len(eligible_rows),
        "conservative_coverage": len(eligible_rows) / population_size,
        "raw_dynamic_model_id": SHADOW_MODEL_ID,
        "conservative_model_id": CHALLENGER_ID,
        "history_threshold": MIN_PRIOR_POINTS_PER_PLAYER,
        "shrinkage_to_neutral": 0.80,
        "development_only": True,
        "no_promotion_claim": True,
        "reports": {
            name: {
                "prediction_count": report["prediction_count"],
                "coverage": report["coverage"],
                "overall": report["overall"],
            }
            for name, report in reports.items()
        },
        "paired_comparison": comparison,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build canonical validation metrics from retained API-Tennis replay"
    )
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = build(replay_path=args.replay, output_dir=args.output_dir)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
