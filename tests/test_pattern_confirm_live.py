from __future__ import annotations

import hashlib
import json

import pytest

from tennis_genome.experiments.pattern_confirm import FrozenMarketCoreFit
from tennis_genome.experiments.pattern_confirm_live import (
    append_live_rows,
    build_live_record,
    evaluate_live_family,
    live_record_as_dict,
    load_live_settlements,
    verify_live_record,
)
from tennis_genome.experiments.pattern_confirm_live_identity import (
    build_identity_mapping,
    parse_sportradar_prematch_event,
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


def _summary(
    *,
    event_id: str = "sr:sport_event:123",
    status: str = "not_started",
    start: str = "2026-09-12T17:00:00+00:00",
) -> dict[str, object]:
    return {
        "sport_event": {
            "id": event_id,
            "start_time": start,
            "start_time_confirmed": True,
            "sport_event_context": {
                "category": {"id": "sr:category:3", "name": "ATP"},
                "competition": {
                    "id": "sr:competition:55",
                    "name": "ATP Miami, USA Men Singles",
                    "type": "singles",
                },
            },
            "competitors": [
                {
                    "id": "sr:competitor:11",
                    "name": "Paul, Tommy",
                    "qualifier": "home",
                    "virtual": False,
                },
                {
                    "id": "sr:competitor:22",
                    "name": "Fritz, Taylor",
                    "qualifier": "away",
                    "virtual": False,
                },
            ],
        },
        "sport_event_status": {"status": status},
    }


def _mapping():
    event = parse_sportradar_prematch_event(_summary())
    return build_identity_mapping(
        market_event_id="odds-event-1",
        market_player_a_name="Tommy Paul",
        market_player_b_name="Taylor Fritz",
        player_a_canonical_id="canonical-a",
        player_b_canonical_id="canonical-b",
        sportradar_event=event,
        method="EXPLICIT_CROSSWALK",
        created_at="2026-09-12T15:00:00+00:00",
    )


def _raw(**updates: object) -> dict[str, object]:
    raw: dict[str, object] = {
        "match_id": "future-1",
        "tour": "ATP",
        "market_provider": "THE_ODDS_API_V4_PINNACLE_V1",
        "market_source": "PINNACLE_H2H_V1",
        "market_event_id": "odds-event-1",
        "player_a_market_name": "Tommy Paul",
        "player_b_market_name": "Taylor Fritz",
        "sportradar_summary": _summary(),
        "provider_match_state": "PREMATCH",
        "provider_snapshot_at": "2026-09-12T16:54:00+00:00",
        "ingested_at": "2026-09-12T16:54:20+00:00",
        "prediction_generated_at": "2026-09-12T16:54:25+00:00",
        "prediction_committed_at": "2026-09-12T16:54:30+00:00",
        "decimal_odds_a": 1.80,
        "decimal_odds_b": 2.10,
        "core_probability_a": 0.55,
        "profile_gap": -0.60,
        "profile_model_sha256": "3" * 64,
        "core_model_sha256": "4" * 64,
    }
    raw.update(updates)
    return raw


def _build(raw: dict[str, object] | None = None):
    return build_live_record(
        _raw() if raw is None else raw,
        fit=_fit(),
        profile_artifact=_profile(),
        core_artifact=_core(),
        identity_mapping=_mapping(),
    )


def _timeline(
    *,
    event_id: str = "sr:sport_event:123",
    actual_start: str | None = "2026-09-12T17:01:00+00:00",
) -> dict[str, object]:
    events: list[dict[str, object]] = []
    if actual_start is not None:
        events.append({"id": 1, "type": "match_started", "time": actual_start})
    return {"sport_event": {"id": event_id}, "timeline": events}


def test_live_intake_computes_market_and_binds_models_and_identity() -> None:
    record = _build()
    expected = (1 / 1.80) / ((1 / 1.80) + (1 / 2.10))
    assert record.market_probability_a == pytest.approx(expected)
    assert record.profile_model_sha256 == "3" * 64
    assert record.core_model_sha256 == "4" * 64
    assert record.identity_mapping_sha256 == _mapping().artifact_sha256
    assert record.market_event_id == "odds-event-1"
    assert record.sportradar_event_id == "sr:sport_event:123"
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
        ({"market_event_id": "wrong"}, "verified identity mapping"),
        ({"player_a_market_name": "Taylor Fritz"}, "player A orientation"),
        (
            {
                "sportradar_summary": _summary(status="live"),
            },
            "pre-match",
        ),
        (
            {
                "provider_snapshot_at": "2026-09-12T16:56:00+00:00",
                "ingested_at": "2026-09-12T16:56:20+00:00",
                "prediction_generated_at": "2026-09-12T16:56:25+00:00",
                "prediction_committed_at": "2026-09-12T16:56:30+00:00",
            },
            "five minutes",
        ),
        ({"ingested_at": "2026-09-12T16:59:30+00:00"}, "stale"),
    ],
)
def test_live_intake_fails_closed(updates: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _build(_raw(**updates))


def test_append_rejects_missing_mapping_and_cross_batch_duplicate() -> None:
    first = _build()
    mapping = _mapping()
    with pytest.raises(ValueError, match="no verified identity mapping"):
        append_live_rows(
            existing_rows=[],
            new_rows=[_raw()],
            identity_mappings={},
            fit=_fit(),
            profile_artifact=_profile(),
            core_artifact=_core(),
        )
    with pytest.raises(ValueError, match="duplicate"):
        append_live_rows(
            existing_rows=[live_record_as_dict(first)],
            new_rows=[_raw()],
            identity_mappings={mapping.market_event_id: mapping},
            fit=_fit(),
            profile_artifact=_profile(),
            core_artifact=_core(),
        )


def test_actual_start_audit_excludes_moved_early_match() -> None:
    record = _build()
    settlements = load_live_settlements(
        [
            {
                "match_id": record.match_id,
                "sportradar_event_id": record.sportradar_event_id,
                "sportradar_timeline": _timeline(actual_start="2026-09-12T16:57:00+00:00"),
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
        item["available_qualifying_n"] == 0 for item in report.core_confirmation["hypotheses"]
    )


def test_missing_match_started_is_auditable_exclusion_not_schedule_fallback() -> None:
    record = _build()
    settlements = load_live_settlements(
        [
            {
                "match_id": record.match_id,
                "sportradar_event_id": record.sportradar_event_id,
                "sportradar_timeline": _timeline(actual_start=None),
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
    assert report.timing_exclusions[0].reason == "ACTUAL_START_UNVERIFIED"
    assert report.timing_exclusions[0].actual_start is None


def test_settlement_identity_mismatch_fails() -> None:
    record = _build()
    settlements = load_live_settlements(
        [
            {
                "match_id": record.match_id,
                "sportradar_event_id": "sr:sport_event:wrong",
                "sportradar_timeline": _timeline(event_id="sr:sport_event:wrong"),
                "outcome_a": False,
                "retirement": False,
                "walkover": False,
            }
        ]
    )
    with pytest.raises(ValueError, match="Sportradar event ID"):
        evaluate_live_family(
            [record],
            settlements,
            fit=_fit(),
            profile_artifact=_profile(),
            core_artifact=_core(),
            ledger_sha256="6" * 64,
            settlement_sha256="7" * 64,
        )


def test_eligible_verified_start_flows_into_existing_confirmation_engine() -> None:
    record = _build()
    settlements = load_live_settlements(
        [
            {
                "match_id": record.match_id,
                "sportradar_event_id": record.sportradar_event_id,
                "sportradar_timeline": _timeline(actual_start="2026-09-12T17:01:00+00:00"),
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
    assert not report.timing_exclusions
    assert all(
        item["available_qualifying_n"] == 1 for item in report.core_confirmation["hypotheses"]
    )


def test_rehashed_semantic_tampering_still_fails_closed() -> None:
    record = _build()
    payload = live_record_as_dict(record)
    payload["player_a_market_name"] = "Wrong Player"
    unsigned = dict(payload)
    unsigned.pop("record_sha256")
    payload["record_sha256"] = hashlib.sha256(
        json.dumps(
            unsigned,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    with pytest.raises(ValueError, match="market player A"):
        verify_live_record(
            payload,
            fit=_fit(),
            profile_artifact=_profile(),
            core_artifact=_core(),
            identity_mapping=_mapping(),
        )
