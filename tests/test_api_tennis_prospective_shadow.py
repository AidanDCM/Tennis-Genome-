from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from tennis_genome.research_workbench.api_tennis_conservative_wta_shadow import (
    CHALLENGER_ID,
)
from tennis_genome.research_workbench.api_tennis_prospective_shadow import (
    ApiTennisChampionCrosswalk,
    ApiTennisProspectiveStateEvidence,
    build_api_tennis_prospective_shadow_bundle,
)
from tennis_genome.research_workbench.challenger import validate_shadow_prediction_set
from tennis_genome.research_workbench.component_challengers import (
    build_component_shadow_bundle,
)

NOW = datetime(2026, 9, 18, 14, 0, tzinfo=UTC)
START = datetime(2026, 9, 18, 18, 0, tzinfo=UTC)
CODE_SHA = "4" * 64
SOURCE_HASHES = ("1" * 64, "2" * 64)
BUNDLE_SHA = "3" * 64


def _component_bundle():
    prediction_dossier = {
        "calculation": {
            "player_a_id": "211684",
            "player_b_id": "214452",
            "production_bundle_sha256": BUNDLE_SHA,
            "prediction": {
                "prediction_id": "FULL-STACK-FORWARD-TEST-API-TENNIS-001",
                "match_id": "sr:sport_event:74574088",
                "tour": "WTA",
                "model_version": "TGE-Independent-v1",
                "prediction_cutoff_at": NOW.isoformat(),
                "p_player_a": 0.604,
                "p_player_b": 0.396,
                "source_manifest_hashes": list(SOURCE_HASHES),
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
    matchup_input = {
        "match_id": "sr:sport_event:74574088",
        "player_a_id": "211684",
        "player_b_id": "214452",
        "prediction_id": "FULL-STACK-FORWARD-TEST-API-TENNIS-001",
        "prediction_cutoff_at": NOW.isoformat(),
        "created_at": NOW.isoformat(),
        "tour": "WTA",
        "best_of": 3,
        "source_manifest_hashes": list(SOURCE_HASHES),
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
    target_resolution = {
        "event_id": "sr:sport_event:74574088",
        "scheduled_start": START.isoformat(),
    }
    return build_component_shadow_bundle(
        prediction_dossier=prediction_dossier,
        matchup_input=matchup_input,
        target_resolution=target_resolution,
        created_at=NOW + timedelta(minutes=5),
        implementation_sha256=CODE_SHA,
        registered_at=NOW - timedelta(days=2),
    )


def _evidence(**overrides: object) -> ApiTennisProspectiveStateEvidence:
    payload: dict[str, object] = {
        "source_artifact_id": 10531692054,
        "state_source_sha256": "a" * 64,
        "target_fixture_sha256": "b" * 64,
        "captured_at": NOW + timedelta(minutes=15),
        "history_through_date": date(2026, 9, 17),
        "event_key": 88001,
        "event_date": date(2026, 9, 18),
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
    }
    payload.update(overrides)
    return ApiTennisProspectiveStateEvidence(**payload)  # type: ignore[arg-type]


def _crosswalk(**overrides: object) -> ApiTennisChampionCrosswalk:
    payload: dict[str, object] = {
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
        "created_at": NOW + timedelta(minutes=10),
    }
    payload.update(overrides)
    return ApiTennisChampionCrosswalk(**payload)  # type: ignore[arg-type]


def _build(
    *,
    evidence: ApiTennisProspectiveStateEvidence | None = None,
    crosswalk: ApiTennisChampionCrosswalk | None = None,
):
    component = _component_bundle()
    return component, build_api_tennis_prospective_shadow_bundle(
        snapshot=component.snapshot,
        evidence=evidence or _evidence(),
        crosswalk=crosswalk or _crosswalk(),
        created_at=NOW + timedelta(minutes=20),
        implementation_sha256=CODE_SHA,
        registered_at=NOW - timedelta(days=1),
    )


def test_prospective_shadow_binds_as_fourth_prediction_on_common_snapshot() -> None:
    component, supplemental = _build()

    assert supplemental.prediction is not None
    prediction = supplemental.prediction
    assert prediction.output.challenger_id == CHALLENGER_ID
    assert prediction.output.p_player_a == pytest.approx(0.56)
    assert prediction.output.p_player_b == pytest.approx(0.44)
    assert prediction.snapshot_sha256 == component.snapshot.semantic_sha256
    assert prediction.output.diagnostics["supplemental_evidence_bound"] is True
    assert prediction.output.diagnostics["orientation_reversed"] is False
    assert supplemental.evidence.semantic_sha256 in prediction.source_manifest_hashes
    assert supplemental.crosswalk.semantic_sha256 in prediction.source_manifest_hashes

    combined = (*component.predictions, prediction)
    validate_shadow_prediction_set(combined)
    assert len(combined) == 4


def test_reversed_crosswalk_reorients_probability_to_champion_player_a() -> None:
    _, supplemental = _build(crosswalk=_crosswalk(orientation="REVERSED"))

    assert supplemental.prediction is not None
    assert supplemental.prediction.output.p_player_a == pytest.approx(0.44)
    assert supplemental.prediction.output.p_player_b == pytest.approx(0.56)
    assert supplemental.prediction.output.diagnostics["orientation_reversed"] is True
    assert supplemental.prediction.output.diagnostics["history_points_a"] == 220
    assert supplemental.prediction.output.diagnostics["history_points_b"] == 220


def test_low_history_match_abstains_without_neutral_pseudo_prediction() -> None:
    evidence = _evidence(prior_serve_points_a=99, prior_return_points_a=100)
    _, supplemental = _build(evidence=evidence)

    assert supplemental.prediction is None
    assert supplemental.registration.challenger_id == CHALLENGER_ID


def test_crosswalk_mismatch_fails_closed() -> None:
    with pytest.raises(ValueError, match="Champion player A mismatch"):
        _build(crosswalk=_crosswalk(champion_player_a_id="wrong"))

    with pytest.raises(ValueError, match="API-Tennis event mismatch"):
        _build(crosswalk=_crosswalk(api_tennis_event_key=99999))


def test_prospective_evidence_must_be_strictly_prior_history_and_pre_start() -> None:
    with pytest.raises(
        ValidationError,
        match="strictly prior-date history",
    ):
        _evidence(history_through_date=date(2026, 9, 18))

    with pytest.raises(ValueError, match="captured before scheduled start"):
        _build(evidence=_evidence(captured_at=START))


def test_prediction_cutoff_tracks_latest_bound_pre_match_input() -> None:
    evidence_time = NOW + timedelta(minutes=25)
    crosswalk_time = NOW + timedelta(minutes=30)
    component = _component_bundle()
    supplemental = build_api_tennis_prospective_shadow_bundle(
        snapshot=component.snapshot,
        evidence=_evidence(captured_at=evidence_time),
        crosswalk=_crosswalk(created_at=crosswalk_time),
        created_at=NOW + timedelta(minutes=35),
        implementation_sha256=CODE_SHA,
        registered_at=NOW - timedelta(days=1),
    )

    assert supplemental.prediction is not None
    assert supplemental.prediction.prediction_cutoff_at == crosswalk_time
