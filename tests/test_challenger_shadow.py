from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from tennis_genome.research_workbench import (
    ChallengerRegistration,
    CommonPreMatchSnapshot,
    ForecastingProcedureSpec,
    ShadowModelOutput,
    ShadowPredictionAnchor,
    build_failure_atlas_record,
    build_league_table,
    build_shadow_prediction,
    settle_shadow_prediction,
    validate_shadow_prediction_set,
    verify_shadow_anchor,
)

NOW = datetime(2026, 9, 16, 14, 0, tzinfo=UTC)
START = datetime(2026, 9, 16, 19, 0, tzinfo=UTC)
SCHEMA_SHA = "1" * 64
SOURCE_SHA = "2" * 64
PAYLOAD_SHA = "3" * 64
CODE_SHA = "4" * 64
TRAIN_SHA = "5" * 64
SETTLEMENT_SHA = "6" * 64


def _procedure(challenger_id: str = "CHALLENGER-BETA-001") -> ForecastingProcedureSpec:
    return ForecastingProcedureSpec(
        procedure_id=challenger_id,
        name="WTA beta calibration shadow",
        version="1",
        input_contract="common-pre-match-snapshot-v1",
        feature_set=("champion_probability",),
        training_method="frozen_beta_calibration",
        calibration="beta",
        prediction_method="predict_proba",
        required_data=("champion_probability",),
        source_code_sha="abcdef1234567890",
        runtime_id="python-3.11-pinned",
        random_seed=None,
    )


def _registration(challenger_id: str = "CHALLENGER-BETA-001") -> ChallengerRegistration:
    return ChallengerRegistration(
        challenger_id=challenger_id,
        challenger_version="1.0.0",
        procedure=_procedure(challenger_id),
        parent_champion_model_version="TGE-Independent-v1",
        feature_schema_sha256=SCHEMA_SHA,
        code_sha256=CODE_SHA,
        training_population_sha256=TRAIN_SHA,
        training_window="2000-2025",
        eligibility_contract="same eligible WTA population as champion when snapshot available",
        promotion_contract="shadow only; no promotion without preregistered protected gate",
        registered_at=NOW - timedelta(days=1),
    )


def _snapshot(
    *,
    snapshot_id: str = "snapshot-001",
    match_id: str = "match-001",
    feature_payload: dict[str, object] | None = None,
) -> CommonPreMatchSnapshot:
    return CommonPreMatchSnapshot(
        snapshot_id=snapshot_id,
        match_id=match_id,
        provider_event_id="sr:sport_event:123",
        tour="WTA",
        player_a_id="player-a",
        player_b_id="player-b",
        scheduled_start=START,
        prediction_cutoff_at=NOW,
        captured_at=NOW + timedelta(seconds=2),
        source_manifest_hashes=(SOURCE_SHA,),
        feature_payload_sha256=PAYLOAD_SHA,
        feature_schema_sha256=SCHEMA_SHA,
        feature_payload=feature_payload or {"champion_probability": 0.62},
    )


def _output(
    *,
    challenger_id: str = "CHALLENGER-BETA-001",
    p_player_a: float = 0.60,
    components: dict[str, float] | None = None,
    diagnostics: dict[str, float | int | bool | None] | None = None,
) -> ShadowModelOutput:
    return ShadowModelOutput(
        challenger_id=challenger_id,
        p_player_a=p_player_a,
        p_player_b=1.0 - p_player_a,
        component_probabilities=components or {"beta_calibrated": p_player_a},
        diagnostics=diagnostics or {"low_history": False, "high_missingness": False},
    )


def _prediction(
    *,
    prediction_id: str = "shadow-001",
    registration: ChallengerRegistration | None = None,
    snapshot: CommonPreMatchSnapshot | None = None,
    output: ShadowModelOutput | None = None,
    created_at: datetime | None = None,
):
    return build_shadow_prediction(
        registration=registration or _registration(),
        snapshot=snapshot or _snapshot(),
        output=output or _output(),
        shadow_prediction_id=prediction_id,
        created_at=created_at or NOW + timedelta(minutes=1),
    )


def test_registration_is_content_addressed_and_frozen() -> None:
    first = _registration()
    second = _registration()

    assert first.semantic_sha256 == second.semantic_sha256
    with pytest.raises(ValidationError):
        first.challenger_version = "2.0.0"  # type: ignore[misc]


def test_common_snapshot_rejects_outcome_and_market_fields() -> None:
    with pytest.raises(ValidationError, match="market/outcome fields"):
        _snapshot(feature_payload={"outcome_player_a_won": True})
    with pytest.raises(ValidationError, match="market/outcome fields"):
        _snapshot(feature_payload={"bookmaker_odds": 1.8})


def test_common_snapshot_requires_strict_pre_start_chronology() -> None:
    with pytest.raises(ValidationError, match="before scheduled_start"):
        CommonPreMatchSnapshot(
            snapshot_id="late-snapshot",
            match_id="match-001",
            provider_event_id="sr:sport_event:123",
            tour="WTA",
            player_a_id="player-a",
            player_b_id="player-b",
            scheduled_start=START,
            prediction_cutoff_at=NOW,
            captured_at=START,
            source_manifest_hashes=(SOURCE_SHA,),
            feature_payload_sha256=PAYLOAD_SHA,
            feature_schema_sha256=SCHEMA_SHA,
            feature_payload={"champion_probability": 0.62},
        )


def test_shadow_prediction_binds_registered_challenger_and_feature_schema() -> None:
    registration = _registration()
    snapshot = _snapshot()
    prediction = _prediction(registration=registration, snapshot=snapshot)

    assert prediction.registration_sha256 == registration.semantic_sha256
    assert prediction.snapshot_sha256 == snapshot.semantic_sha256
    assert prediction.source_manifest_hashes == snapshot.source_manifest_hashes

    with pytest.raises(ValueError, match="challenger output"):
        _prediction(
            registration=registration,
            snapshot=snapshot,
            output=_output(challenger_id="OTHER-CHALLENGER"),
        )

    bad_registration = ChallengerRegistration(
        **{
            **registration.model_dump(),
            "feature_schema_sha256": "9" * 64,
        }
    )
    with pytest.raises(ValueError, match="feature schema"):
        _prediction(registration=bad_registration, snapshot=snapshot)


def test_late_challenger_prediction_is_rejected() -> None:
    with pytest.raises(ValidationError, match="not prospective"):
        _prediction(created_at=START)


def test_shadow_prediction_set_rejects_duplicate_ids_and_mixed_snapshots() -> None:
    first = _prediction(prediction_id="shadow-001")
    duplicate = _prediction(prediction_id="shadow-001")
    with pytest.raises(ValueError, match="duplicate shadow prediction IDs"):
        validate_shadow_prediction_set((first, duplicate))

    second_registration = _registration("CHALLENGER-SECOND-001")
    second_output = _output(challenger_id="CHALLENGER-SECOND-001", p_player_a=0.58)
    second = _prediction(
        prediction_id="shadow-002",
        registration=second_registration,
        output=second_output,
        snapshot=_snapshot(snapshot_id="snapshot-002", match_id="match-002"),
    )
    with pytest.raises(ValueError, match="share one snapshot identity"):
        validate_shadow_prediction_set((first, second))


def test_shadow_anchor_requires_exact_hash_unedited_bot_commitment_and_prestart() -> None:
    prediction = _prediction()
    anchor = ShadowPredictionAnchor(
        shadow_prediction_id=prediction.shadow_prediction_id,
        shadow_prediction_sha256=prediction.semantic_sha256,
        anchor_id="comment-123",
        workflow_run_id=123456,
        created_at=NOW + timedelta(minutes=2),
        updated_at=NOW + timedelta(minutes=2),
    )
    verify_shadow_anchor(prediction=prediction, anchor=anchor)

    wrong_hash = anchor.model_copy(update={"shadow_prediction_sha256": "9" * 64})
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_shadow_anchor(prediction=prediction, anchor=wrong_hash)

    with pytest.raises(ValidationError, match="unedited"):
        ShadowPredictionAnchor(
            shadow_prediction_id=prediction.shadow_prediction_id,
            shadow_prediction_sha256=prediction.semantic_sha256,
            anchor_id="edited-comment",
            workflow_run_id=123456,
            created_at=NOW + timedelta(minutes=2),
            updated_at=NOW + timedelta(minutes=3),
        )

    late_anchor = anchor.model_copy(
        update={"created_at": START, "updated_at": START}
    )
    with pytest.raises(ValueError, match="before scheduled start"):
        verify_shadow_anchor(prediction=prediction, anchor=late_anchor)


def test_settlement_requires_exact_prediction_orientation_and_scores_properly() -> None:
    prediction = _prediction(output=_output(p_player_a=0.60))
    settlement = settle_shadow_prediction(
        prediction=prediction,
        winner_player_id="player-b",
        settled_at=START + timedelta(hours=2),
        settlement_evidence_sha256=SETTLEMENT_SHA,
    )

    assert settlement.correctness == 0
    assert settlement.brier == pytest.approx(0.36)
    assert settlement.log_loss == pytest.approx(-math.log(0.40))
    assert settlement.shadow_prediction_sha256 == prediction.semantic_sha256

    with pytest.raises(ValueError, match="prediction orientation"):
        settle_shadow_prediction(
            prediction=prediction,
            winner_player_id="unrelated-player",
            settled_at=START + timedelta(hours=2),
            settlement_evidence_sha256=SETTLEMENT_SHA,
        )


def test_league_table_requires_exact_hash_linkage() -> None:
    first = _prediction(prediction_id="shadow-001", output=_output(p_player_a=0.60))
    second_registration = _registration("CHALLENGER-SECOND-001")
    second = _prediction(
        prediction_id="shadow-002",
        registration=second_registration,
        output=_output(challenger_id="CHALLENGER-SECOND-001", p_player_a=0.40),
    )
    first_settlement = settle_shadow_prediction(
        prediction=first,
        winner_player_id="player-b",
        settled_at=START + timedelta(hours=2),
        settlement_evidence_sha256=SETTLEMENT_SHA,
    )
    second_settlement = settle_shadow_prediction(
        prediction=second,
        winner_player_id="player-b",
        settled_at=START + timedelta(hours=2),
        settlement_evidence_sha256=SETTLEMENT_SHA,
    )

    rows = build_league_table(
        predictions=(first, second),
        settlements=(first_settlement, second_settlement),
    )
    by_id = {row.challenger_id: row for row in rows}
    assert by_id["CHALLENGER-BETA-001"].accuracy == 0.0
    assert by_id["CHALLENGER-SECOND-001"].accuracy == 1.0

    tampered = first_settlement.model_copy(
        update={"shadow_prediction_sha256": "9" * 64}
    )
    with pytest.raises(ValueError, match="hash mismatch"):
        build_league_table(predictions=(first,), settlements=(tampered,))


def test_failure_atlas_separates_pre_match_and_post_result_information() -> None:
    prediction = _prediction(
        output=_output(
            p_player_a=0.70,
            components={"core": 0.72, "pointsim": 0.50},
            diagnostics={"low_history": True, "high_missingness": False},
        )
    )
    settlement = settle_shadow_prediction(
        prediction=prediction,
        winner_player_id="player-b",
        settled_at=START + timedelta(hours=2),
        settlement_evidence_sha256=SETTLEMENT_SHA,
    )
    atlas = build_failure_atlas_record(
        prediction=prediction,
        settlement=settlement,
        post_result_diagnostics={"double_faults_player_a": 10, "score": "2-6 5-7"},
    )

    assert atlas.evidence_role == "POST_RESULT_DIAGNOSTIC_ONLY"
    assert atlas.pre_match_component_probabilities == {"core": 0.72, "pointsim": 0.50}
    assert atlas.post_result_diagnostics["double_faults_player_a"] == 10
    assert atlas.deterministic_tags == (
        "HIGH_COMPONENT_DISAGREEMENT",
        "HIGH_CONFIDENCE_MISS",
        "LOW_HISTORY",
        "WINNER_MISS",
    )
