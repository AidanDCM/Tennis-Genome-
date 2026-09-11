from __future__ import annotations

import pytest

from tennis_genome.experiments.pattern_confirm import FrozenMarketCoreFit
from tennis_genome.experiments.pattern_confirm_live import (
    append_live_rows,
    build_live_record,
    evaluate_live_family,
    load_live_settlements,
)
from tennis_genome.experiments.pattern_confirm_production import (
    CoreProductionArtifact,
    ProfileProductionArtifact,
)


def _fit() -> FrozenMarketCoreFit:
    return FrozenMarketCoreFit(
        experiment_id="PATTERN-CONFIRM-001",
        version="pattern-confirm-v1",
        source_bundle_sha256="d" * 64,
        source_claim="synthetic",
        training_rows_sha256="e" * 64,
        training_n=100,
        training_start_year=2016,
        training_end_year=2025,
        intercept=0.0,
        market_logit_slope=1.0,
        core_logit_slope=0.0,
        artifact_sha256="f" * 64,
    )


def _profile() -> ProfileProductionArtifact:
    return ProfileProductionArtifact(
        experiment_id="PROFILE-PRODUCTION-001",
        version="pattern-confirm-production-v1",
        tour="ATP",
        representation="strict",
        training_end_year=2025,
        training_n=100,
        training_rows_sha256="1" * 64,
        canonical_manifest_sha256="2" * 64,
        state_semantics="strictly-earlier-date-state-v1",
        feature_names=("x",),
        imputer_statistics=(0.0,),
        scaler_mean=(0.0,),
        scaler_scale=(1.0,),
        logistic_coefficients=(1.0,),
        elo_initial_rating=1500.0,
        elo_k_factor=32.0,
        elo_scale=400.0,
        artifact_sha256="3" * 64,
    )


def _core() -> CoreProductionArtifact:
    return CoreProductionArtifact(
        experiment_id="CORE-PRODUCTION-001",
        version="pattern-confirm-production-v1",
        tour="ATP",
        representation="strict_a",
        training_end_year=2025,
        training_n=100,
        training_rows_sha256="1" * 64,
        canonical_manifest_sha256="2" * 64,
        state_semantics="strictly-earlier-date-state-v1",
        feature_names=("x",),
        imputer_statistics=(0.0,),
        imputer_indicator_features=(),
        scaler_mean=(0.0,),
        scaler_scale=(1.0,),
        logistic_coefficients=(1.0,),
        logistic_intercept=0.0,
        artifact_sha256="4" * 64,
    )


def _raw(**updates: object) -> dict[str, object]:
    raw: dict[str, object] = {
        "match_id": "future-1",
        "tour": "ATP",
        "scheduled_start": "2026-09-12T13:00:00-04:00",
        "market_provider": "THE_ODDS_API_V4_PINNACLE_V1",
        "market_source": "PINNACLE_H2H_V1",
        "provider_event_id": "event-1",
        "player_a_provider_id": "pa",
        "player_b_provider_id": "pb",
        "player_a_id": "canonical-a",
        "player_b_id": "canonical-b",
        "identity_mapping_sha256": "5" * 64,
        "provider_match_state": "PREMATCH",
        "provider_snapshot_at": "2026-09-12T12:54:00-04:00",
        "ingested_at": "2026-09-12T12:54:20-04:00",
        "prediction_generated_at": "2026-09-12T12:54:25-04:00",
        "prediction_committed_at": "2026-09-12T12:54:30-04:00",
        "decimal_odds_a": 1.80,
        "decimal_odds_b": 2.10,
        "core_probability_a": 0.55,
        "profile_gap": -0.60,
        "profile_model_sha256": "3" * 64,
        "core_model_sha256": "4" * 64,
    }
    raw.update(updates)
    return raw


def test_live_intake_computes_market_and_binds_models() -> None:
    record = build_live_record(_raw(), fit=_fit(), profile_artifact=_profile(), core_artifact=_core())
    expected = (1 / 1.80) / ((1 / 1.80) + (1 / 2.10))
    assert record.market_probability_a == pytest.approx(expected)
    assert record.profile_model_sha256 == "3" * 64
    assert record.core_model_sha256 == "4" * 64
    assert set(record.core_record.matched_hypotheses) == {
        "PC-ATP-PG-LOW",
        "PC-ATP-PG-ABS-HIGH",
    }


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"market_provider": "OTHER"}, "frozen Pinnacle"),
        ({"provider_match_state": "LIVE"}, "PREMATCH"),
        ({"decimal_odds_a": 1.0}, "decimal odds"),
        ({"profile_model_sha256": "9" * 64}, "Profile artifact"),
        ({"core_model_sha256": "9" * 64}, "Core artifact"),
        ({"provider_snapshot_at": "2026-09-12T12:56:00-04:00"}, "five minutes"),
        ({"ingested_at": "2026-09-12T12:59:30-04:00"}, "stale"),
    ],
)
def test_live_intake_fails_closed(updates: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        build_live_record(
            _raw(**updates), fit=_fit(), profile_artifact=_profile(), core_artifact=_core()
        )


def test_append_rejects_cross_batch_duplicate() -> None:
    first = build_live_record(_raw(), fit=_fit(), profile_artifact=_profile(), core_artifact=_core())
    from tennis_genome.experiments.pattern_confirm_live import live_record_as_dict

    with pytest.raises(ValueError, match="duplicate"):
        append_live_rows(
            existing_rows=[live_record_as_dict(first)],
            new_rows=[_raw()],
            fit=_fit(),
            profile_artifact=_profile(),
            core_artifact=_core(),
        )


def test_actual_start_audit_excludes_moved_early_match() -> None:
    record = build_live_record(_raw(), fit=_fit(), profile_artifact=_profile(), core_artifact=_core())
    settlements = load_live_settlements(
        [
            {
                "match_id": record.match_id,
                "provider_event_id": record.provider_event_id,
                "actual_start": "2026-09-12T12:57:00-04:00",
                "outcome_a": True,
                "retirement": False,
                "walkover": False,
            }
        ]
    )
    report = evaluate_live_family(
        [record],
        settlements,
        fit=_fit(),
        profile_artifact=_profile(),
        core_artifact=_core(),
        ledger_sha256="6" * 64,
        settlement_sha256="7" * 64,
    )
    assert len(report.timing_exclusions) == 1
    assert report.timing_exclusions[0].reason == "PROVIDER_SNAPSHOT_NOT_T_MINUS_5"
    assert all(
        item["available_qualifying_n"] == 0
        for item in report.core_confirmation["hypotheses"]
    )


def test_settlement_identity_mismatch_fails() -> None:
    record = build_live_record(_raw(), fit=_fit(), profile_artifact=_profile(), core_artifact=_core())
    settlements = load_live_settlements(
        [
            {
                "match_id": record.match_id,
                "provider_event_id": "wrong-event",
                "actual_start": "2026-09-12T13:01:00-04:00",
                "outcome_a": False,
                "retirement": False,
                "walkover": False,
            }
        ]
    )
    with pytest.raises(ValueError, match="provider_event_id"):
        evaluate_live_family(
            [record],
            settlements,
            fit=_fit(),
            profile_artifact=_profile(),
            core_artifact=_core(),
            ledger_sha256="6" * 64,
            settlement_sha256="7" * 64,
        )
