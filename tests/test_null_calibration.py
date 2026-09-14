from __future__ import annotations

import pytest
from pydantic import ValidationError

from tennis_genome.research_workbench.null_calibration import (
    NullCalibrationSpec,
    run_null_calibration_campaign,
)

_SOURCE_SHA = "27f936bebd52437173721feb65d007d931975097"


def _spec(**overrides: object) -> NullCalibrationSpec:
    payload: dict[str, object] = {
        "campaign_id": "null-health-001",
        "seeds": (11, 22, 33, 44, 55),
        "n_per_world": 700,
        "source_code_sha": _SOURCE_SHA,
        "brier_material_gain": 0.05,
        "log_loss_material_gain": 0.10,
        "max_false_promotion_rate": 0.80,
        "confidence_level": 0.95,
    }
    payload.update(overrides)
    return NullCalibrationSpec(**payload)


def test_null_campaign_is_deterministic_and_hash_bound() -> None:
    spec = _spec()
    first = run_null_calibration_campaign(spec)
    second = run_null_calibration_campaign(spec)

    assert first.semantic_sha256 == second.semantic_sha256
    assert first.campaign_spec_sha256 == spec.semantic_sha256
    assert first.n_worlds == len(spec.seeds)
    assert tuple(result.seed for result in first.results) == spec.seeds


def test_oracle_null_does_not_clear_deliberately_large_material_thresholds() -> None:
    report = run_null_calibration_campaign(_spec())

    assert report.n_false_promotions == 0
    assert report.false_promotion_rate == 0.0
    assert report.status == "HEALTHY"
    assert all(not result.any_false_promotion for result in report.results)


def test_small_zero_failure_campaign_cannot_certify_aggressive_error_ceiling() -> None:
    report = run_null_calibration_campaign(
        _spec(max_false_promotion_rate=0.10)
    )

    assert report.n_false_promotions == 0
    assert report.false_promotion_rate == 0.0
    assert report.upper_confidence_bound > 0.10
    assert report.status == "FAILED"


def test_campaign_spec_requires_registered_unique_seed_family_and_positive_thresholds() -> None:
    with pytest.raises(ValidationError, match="at least five"):
        _spec(seeds=(1, 2, 3, 4))

    with pytest.raises(ValidationError, match="unique"):
        _spec(seeds=(1, 2, 3, 4, 4))

    with pytest.raises(ValidationError, match="500 rows"):
        _spec(n_per_world=499)

    with pytest.raises(ValidationError, match="brier_material_gain"):
        _spec(brier_material_gain=0.0)

    with pytest.raises(ValidationError, match="log_loss_material_gain"):
        _spec(log_loss_material_gain=-0.1)


def test_campaign_result_exposes_challenger_specific_proper_score_gains() -> None:
    report = run_null_calibration_campaign(_spec())
    result = report.results[0]

    assert isinstance(result.calibration_brier_gain, float)
    assert isinstance(result.calibration_log_loss_gain, float)
    assert isinstance(result.interaction_brier_gain, float)
    assert isinstance(result.interaction_log_loss_gain, float)
    assert result.any_false_promotion == (
        result.calibration_false_promotion or result.interaction_false_promotion
    )
