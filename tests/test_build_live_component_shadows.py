from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.build_live_component_shadows import build
from tennis_genome.research_workbench.api_tennis_conservative_wta_shadow import (
    CHALLENGER_ID,
)
from tennis_genome.research_workbench.api_tennis_prospective_shadow import (
    DEEP_HISTORY_CHALLENGER_ID,
)

CREATED = datetime(2026, 9, 18, 16, 0, tzinfo=UTC)
START = datetime(2026, 9, 18, 19, 0, tzinfo=UTC)


def _write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _champion_inputs(root: Path) -> tuple[Path, Path, Path]:
    prediction = {
        "calculation": {
            "player_a_id": "211684",
            "player_b_id": "214452",
            "production_bundle_sha256": "3" * 64,
            "prediction": {
                "prediction_id": "FULL-STACK-FORWARD-SCRIPT-001",
                "match_id": "sr:sport_event:74574088",
                "tour": "WTA",
                "model_version": "TGE-Independent-v1",
                "prediction_cutoff_at": "2026-09-18T15:30:00+00:00",
                "p_player_a": 0.604,
                "p_player_b": 0.396,
                "source_manifest_hashes": ["1" * 64, "2" * 64],
                "component_probabilities": {
                    "strict_core_v1": 0.641,
                    "strict_core_geometry_historical_alignment_k100": 0.614,
                    "pointsim_conditional_meta_input": 0.590,
                    "pointsim_conditional_meta_final": 0.604,
                },
                "diagnostics": {
                    "model_disagreement": 0.082,
                    "alignment_missing_fraction": 0.0625,
                    "pointsim_min_prior_point_history": 710,
                },
            },
        }
    }
    matchup = {
        "match_id": "sr:sport_event:74574088",
        "player_a_id": "211684",
        "player_b_id": "214452",
        "prediction_id": "FULL-STACK-FORWARD-SCRIPT-001",
        "prediction_cutoff_at": "2026-09-18T15:30:00+00:00",
        "created_at": "2026-09-18T15:30:00+00:00",
        "tour": "WTA",
        "best_of": 3,
        "source_manifest_hashes": ["1" * 64, "2" * 64],
        "foundational": {
            "elo_logit": 0.21,
            "form_result_30_diff": 0.11,
            "surface_hard_elo": 0.21,
            "serve_return_edge": 0.03,
            "h2h_edge": 0.08,
            "h2h_weighted_edge": 0.06,
            "opposite_hand_serve_edge": 0.01,
        },
        "serve_return": {
            "probability_a_serve_point": 0.585,
            "probability_b_serve_point": 0.568,
        },
        "profile_pair": None,
    }
    target = {
        "event_id": "sr:sport_event:74574088",
        "scheduled_start": START.isoformat(),
    }
    return (
        _write(root / "prediction.json", prediction),
        _write(root / "matchup.json", matchup),
        _write(root / "target.json", target),
    )


def _supplemental_inputs(root: Path) -> tuple[Path, Path]:
    evidence = {
        "schema_version": "tennis-genome-api-tennis-prospective-state-v1",
        "source_artifact_id": 10531692054,
        "state_source_sha256": "a" * 64,
        "target_fixture_sha256": "b" * 64,
        "captured_at": "2026-09-18T15:45:00+00:00",
        "history_through_date": "2026-09-17",
        "event_key": 88001,
        "event_date": "2026-09-18",
        "tour": "WTA",
        "player_a_key": 101,
        "player_b_key": 202,
        "player_a_name": "API A",
        "player_b_name": "API B",
        "probability_a_serve_point": 0.65,
        "probability_b_serve_point": 0.57,
        "probability_a_match": 0.80,
        "prior_serve_points_a": 120,
        "prior_serve_points_b": 130,
        "prior_return_points_a": 100,
        "prior_return_points_b": 90,
        "historical_actual_start_admissible": False,
    }
    crosswalk = {
        "schema_version": "tennis-genome-api-tennis-champion-crosswalk-v1",
        "champion_match_id": "sr:sport_event:74574088",
        "champion_provider_event_id": "sr:sport_event:74574088",
        "champion_player_a_id": "211684",
        "champion_player_b_id": "214452",
        "api_tennis_event_key": 88001,
        "api_tennis_player_a_key": 101,
        "api_tennis_player_b_key": 202,
        "orientation": "DIRECT",
        "mapping_basis": "EXPLICIT_PROVIDER_ID",
        "mapping_evidence_sha256": "c" * 64,
        "created_at": "2026-09-18T15:40:00+00:00",
    }
    return (
        _write(root / "api-tennis-prospective-state.json", evidence),
        _write(root / "api-tennis-champion-crosswalk.json", crosswalk),
    )


def test_live_shadow_builder_preserves_base_three_without_supplemental_input(
    tmp_path: Path,
) -> None:
    prediction, matchup, target = _champion_inputs(tmp_path)
    output = tmp_path / "base-shadow"

    manifest = build(
        prediction_dossier_path=prediction,
        matchup_input_path=matchup,
        target_resolution_path=target,
        output_dir=output,
        created_at=CREATED,
    )

    assert manifest["prediction_count"] == 3
    assert manifest["registration_count"] == 3
    assert manifest["supplemental_api_tennis"] is None
    assert len(list((output / "predictions").glob("*.json"))) == 3


def test_live_shadow_builder_adds_eligible_api_tennis_fourth_prediction(
    tmp_path: Path,
) -> None:
    prediction, matchup, target = _champion_inputs(tmp_path)
    evidence, crosswalk = _supplemental_inputs(tmp_path)
    output = tmp_path / "supplemental-shadow"

    manifest = build(
        prediction_dossier_path=prediction,
        matchup_input_path=matchup,
        target_resolution_path=target,
        output_dir=output,
        created_at=CREATED,
        api_tennis_evidence_path=evidence,
        api_tennis_crosswalk_path=crosswalk,
    )

    assert manifest["prediction_count"] == 4
    assert manifest["registration_count"] == 4
    assert manifest["supplemental_api_tennis"]["abstained"] is False
    assert manifest["supplemental_api_tennis"]["deep_history_registered"] is False
    assert manifest["supplemental_api_tennis"]["deep_history_abstained"] is None
    prediction_path = output / "predictions" / f"{CHALLENGER_ID}.json"
    payload = json.loads(prediction_path.read_text(encoding="utf-8"))
    assert payload["output"]["p_player_a"] == pytest.approx(0.56)
    assert payload["output"]["p_player_b"] == pytest.approx(0.44)
    assert len(manifest["anchor_requests"]) == 4
    assert (output / "supplemental-api-tennis" / "bundle.json").is_file()


def test_live_shadow_builder_requires_evidence_and_crosswalk_as_a_pair(
    tmp_path: Path,
) -> None:
    prediction, matchup, target = _champion_inputs(tmp_path)
    evidence, _ = _supplemental_inputs(tmp_path)

    with pytest.raises(ValueError, match="must be supplied together"):
        build(
            prediction_dossier_path=prediction,
            matchup_input_path=matchup,
            target_resolution_path=target,
            output_dir=tmp_path / "invalid-shadow",
            created_at=CREATED,
            api_tennis_evidence_path=evidence,
        )



def test_live_shadow_builder_adds_deep_history_fifth_prediction(
    tmp_path: Path,
) -> None:
    prediction, matchup, target = _champion_inputs(tmp_path)
    evidence, crosswalk = _supplemental_inputs(tmp_path)
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload.update(
        {
            "prior_serve_points_a": 300,
            "prior_return_points_a": 300,
            "prior_serve_points_b": 300,
            "prior_return_points_b": 300,
        }
    )
    evidence.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "deep-supplemental-shadow"

    manifest = build(
        prediction_dossier_path=prediction,
        matchup_input_path=matchup,
        target_resolution_path=target,
        output_dir=output,
        created_at=datetime(2026, 9, 18, 16, 18, tzinfo=UTC),
        api_tennis_evidence_path=evidence,
        api_tennis_crosswalk_path=crosswalk,
    )

    assert manifest["prediction_count"] == 5
    assert manifest["registration_count"] == 5
    assert manifest["supplemental_api_tennis"]["abstained"] is False
    assert manifest["supplemental_api_tennis"]["deep_history_registered"] is True
    assert manifest["supplemental_api_tennis"]["deep_history_abstained"] is False
    deep_path = output / "predictions" / f"{DEEP_HISTORY_CHALLENGER_ID}.json"
    deep = json.loads(deep_path.read_text(encoding="utf-8"))
    assert deep["output"]["p_player_a"] == pytest.approx(0.56)
    assert (output / "supplemental-api-tennis" / "deep-history-bundle.json").is_file()


def test_live_shadow_workflows_allow_three_four_or_five_predictions() -> None:
    anchor_workflow = Path(
        ".github/workflows/challenger_shadow_from_prediction_artifact.yml"
    ).read_text(encoding="utf-8")
    settlement_workflow = Path(
        ".github/workflows/challenger_shadow_settlement_finalize.yml"
    ).read_text(encoding="utf-8")

    assert "prediction_count not in {3, 4, 5}" in anchor_workflow
    assert "registration_count != 5" in anchor_workflow
    assert "expected not in {3, 4, 5}" in anchor_workflow
    assert "expected not in {3, 4, 5}" in settlement_workflow
