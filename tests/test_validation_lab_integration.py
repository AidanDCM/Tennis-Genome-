from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.aggregate_forward_validation import aggregate
from scripts.build_api_tennis_validation_lab import build as build_api_lab


def _score(
    *,
    event_key: int,
    event_date: str,
    probability: float,
    winner_side: str,
    prior_points_each: int,
) -> dict[str, object]:
    half = prior_points_each // 2
    return {
        "event_key": event_key,
        "event_date": event_date,
        "tour": "WTA",
        "probability_a_match": probability,
        "winner_side": winner_side,
        "prior_serve_points_a": half,
        "prior_serve_points_b": half,
        "prior_return_points_a": prior_points_each - half,
        "prior_return_points_b": prior_points_each - half,
        "any_history": prior_points_each > 0,
        "both_players_history": prior_points_each > 0,
    }


def test_api_tennis_validation_lab_reports_population_coverage_and_paired_shrinkage(
    tmp_path: Path,
) -> None:
    replay_path = tmp_path / "replay.json"
    replay_path.write_text(
        json.dumps(
            {
                "replay_id": "API-TENNIS-FILTERED-SHADOW-REPLAY-001",
                "scores": [
                    _score(
                        event_key=1,
                        event_date="2026-08-17",
                        probability=0.90,
                        winner_side="A",
                        prior_points_each=100,
                    ),
                    _score(
                        event_key=2,
                        event_date="2026-08-18",
                        probability=0.80,
                        winner_side="A",
                        prior_points_each=300,
                    ),
                    _score(
                        event_key=3,
                        event_date="2026-08-19",
                        probability=0.75,
                        winner_side="B",
                        prior_points_each=500,
                    ),
                    _score(
                        event_key=4,
                        event_date="2026-08-20",
                        probability=0.30,
                        winner_side="B",
                        prior_points_each=1000,
                    ),
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "lab"

    manifest = build_api_lab(replay_path=replay_path, output_dir=output_dir)

    assert manifest["wta_population_count"] == 4
    assert manifest["conservative_eligible_count"] == 3
    assert manifest["conservative_coverage"] == pytest.approx(0.75)
    assert manifest["development_only"] is True
    assert manifest["no_promotion_claim"] is True

    conservative = json.loads(
        (output_dir / "reports/conservative_wta.json").read_text(encoding="utf-8")
    )
    raw_eligible = json.loads(
        (output_dir / "reports/raw_dynamic_conservative_eligible.json").read_text(
            encoding="utf-8"
        )
    )
    comparison = json.loads(
        (output_dir / "paired-conservative-vs-raw.json").read_text(encoding="utf-8")
    )

    assert conservative["prediction_count"] == 3
    assert conservative["coverage"] == pytest.approx(0.75)
    assert raw_eligible["prediction_count"] == 3
    assert comparison["n"] == 3
    assert comparison["baseline_model_id"] == "TGE-SHADOW-API-TENNIS-DYNAMIC-SR-V1"
    assert comparison["candidate_model_id"] == "TGE-CHALLENGER-WTA-DYNAMIC-SR-SHRUNK-V1"


def _write_observation(
    root: Path,
    *,
    artifact: str,
    model_id: str,
    match_id: str,
    probability: float,
    outcome: bool,
) -> None:
    path = root / artifact / "shadow-finalized" / "validation-observations"
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{model_id}.json").write_text(
        json.dumps(
            {
                "model_id": model_id,
                "match_id": match_id,
                "event_date": "2026-09-18",
                "probability_a": probability,
                "outcome_a_won": outcome,
                "component_probabilities": {},
                "pre_match_diagnostics": {},
                "tags": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_forward_aggregate_compares_each_challenger_on_identity_matched_population(
    tmp_path: Path,
) -> None:
    settlement_root = tmp_path / "settlements"
    _write_observation(
        settlement_root,
        artifact="a1",
        model_id="TGE-SHADOW-IDENTITY-V1",
        match_id="m1",
        probability=0.70,
        outcome=True,
    )
    _write_observation(
        settlement_root,
        artifact="a1",
        model_id="TGE-SHADOW-GEOMETRY-V1",
        match_id="m1",
        probability=0.65,
        outcome=True,
    )
    _write_observation(
        settlement_root,
        artifact="a2",
        model_id="TGE-SHADOW-IDENTITY-V1",
        match_id="m2",
        probability=0.60,
        outcome=False,
    )
    _write_observation(
        settlement_root,
        artifact="a2",
        model_id="TGE-SHADOW-GEOMETRY-V1",
        match_id="m2",
        probability=0.55,
        outcome=False,
    )

    output_dir = tmp_path / "aggregate"
    manifest = aggregate(settlement_root=settlement_root, output_dir=output_dir)

    assert manifest["population_match_count"] == 2
    assert manifest["model_prediction_counts"] == {
        "TGE-SHADOW-GEOMETRY-V1": 2,
        "TGE-SHADOW-IDENTITY-V1": 2,
    }
    assert manifest["model_coverage"] == {
        "TGE-SHADOW-GEOMETRY-V1": 1.0,
        "TGE-SHADOW-IDENTITY-V1": 1.0,
    }
    comparison = json.loads(
        (
            output_dir
            / "paired-comparisons"
            / "TGE-SHADOW-GEOMETRY-V1-vs-TGE-SHADOW-IDENTITY-V1.json"
        ).read_text(encoding="utf-8")
    )
    assert comparison["n"] == 2


def test_api_tennis_replay_workflow_uploads_canonical_validation_lab() -> None:
    text = Path(".github/workflows/api_tennis_filtered_replay.yml").read_text(
        encoding="utf-8"
    )

    assert "Build canonical validation lab from retained replay" in text
    assert "scripts/build_api_tennis_validation_lab.py" in text
    assert "api-tennis-validation-lab/manifest.json" in text
    assert "paired-conservative-vs-raw.json" in text


def test_forward_validation_workflow_is_scheduled_and_retains_reports() -> None:
    text = Path(".github/workflows/forward_validation_aggregate.yml").read_text(
        encoding="utf-8"
    )

    assert 'cron: "17 6 * * *"' in text
    assert "scripts/aggregate_forward_validation.py" in text
    assert "challenger-shadow-settlement-" in text
    assert "forward-validation-aggregate-${{ github.run_id }}" in text
    assert "retention-days: 90" in text



def test_shadow_settlement_workflow_requires_validation_artifacts() -> None:
    text = Path(
        ".github/workflows/challenger_shadow_settlement_finalize.yml"
    ).read_text(encoding="utf-8")

    assert "validation-observations" in text
    assert "validation-reports" in text
    assert "validation observation count differs from prediction count" in text
    assert "validation report count differs from prediction count" in text
    assert "validation_report_sha256" in text
