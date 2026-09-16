from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from tennis_genome.research_workbench.component_challengers import (
    build_component_shadow_bundle,
    canonical_record_json,
)

NOW = datetime(2026, 9, 16, 16, 40, tzinfo=UTC)
START = datetime(2026, 9, 16, 19, 0, tzinfo=UTC)
SOURCE_HASHES = ("1" * 64, "2" * 64)
BUNDLE_SHA = "3" * 64
CODE_SHA = "4" * 64


def _prediction_dossier() -> dict[str, object]:
    return {
        "calculation": {
            "player_a_id": "211684",
            "player_b_id": "214452",
            "production_bundle_sha256": BUNDLE_SHA,
            "prediction": {
                "prediction_id": "FULL-STACK-FORWARD-TEST-001",
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


def _matchup_input() -> dict[str, object]:
    return {
        "match_id": "sr:sport_event:74574088",
        "player_a_id": "211684",
        "player_b_id": "214452",
        "prediction_id": "FULL-STACK-FORWARD-TEST-001",
        "prediction_cutoff_at": NOW.isoformat(),
        "created_at": NOW.isoformat(),
        "tour": "WTA",
        "best_of": 3,
        "source_manifest_hashes": list(SOURCE_HASHES),
        "foundational": {
            "elo_logit": 0.21,
            "form_result_30_diff": 0.11,
            "surface_hard_elo": 0.21,
        },
        "serve_return": {
            "probability_a_serve_point": 0.585,
            "probability_b_serve_point": 0.568,
        },
        "profile_pair": None,
    }


def _target_resolution() -> dict[str, object]:
    return {
        "event_id": "sr:sport_event:74574088",
        "scheduled_start": START.isoformat(),
    }


def _build(**overrides: object):
    payload = {
        "prediction_dossier": _prediction_dossier(),
        "matchup_input": _matchup_input(),
        "target_resolution": _target_resolution(),
        "created_at": NOW + timedelta(minutes=5),
        "implementation_sha256": CODE_SHA,
        "registered_at": NOW - timedelta(days=1),
    }
    payload.update(overrides)
    return build_component_shadow_bundle(**payload)  # type: ignore[arg-type]


def test_component_shadow_bundle_has_three_same_snapshot_predictions() -> None:
    bundle = _build()

    assert len(bundle.registrations) == 3
    assert len(bundle.predictions) == 3
    assert {item.snapshot_sha256 for item in bundle.predictions} == {
        bundle.snapshot.semantic_sha256
    }
    probabilities = {
        item.output.challenger_id: item.output.p_player_a for item in bundle.predictions
    }
    assert probabilities == {
        "TGE-SHADOW-GEOMETRY-V1": pytest.approx(0.614),
        "TGE-SHADOW-IDENTITY-V1": pytest.approx(0.604),
        "TGE-SHADOW-POINTSIM-V1": pytest.approx(0.590),
    }


def test_component_shadow_bundle_is_deterministic_for_identical_inputs() -> None:
    first = _build()
    second = _build()

    assert first.semantic_sha256 == second.semantic_sha256
    assert [item.semantic_sha256 for item in first.predictions] == [
        item.semantic_sha256 for item in second.predictions
    ]
    for item in first.predictions:
        canonical = canonical_record_json(item)
        assert canonical == canonical_record_json(item)


def test_component_shadow_bundle_binds_target_and_orientation() -> None:
    target = _target_resolution()
    target["event_id"] = "sr:sport_event:999"
    with pytest.raises(ValueError, match="provider target disagree"):
        _build(target_resolution=target)

    matchup = _matchup_input()
    matchup["player_a_id"] = "wrong"
    with pytest.raises(ValueError, match="player A orientation"):
        _build(matchup_input=matchup)


def test_component_shadow_bundle_rejects_late_capture() -> None:
    with pytest.raises(ValidationError, match="before scheduled_start"):
        _build(created_at=START)


def test_component_shadow_bundle_contains_no_fair_price_or_market_payload() -> None:
    bundle = _build()
    payload = bundle.snapshot.feature_payload

    assert "fair_decimal_odds" not in payload
    assert "market" not in str(payload).lower()
    assert payload["champion_probability_a"] == pytest.approx(0.604)
