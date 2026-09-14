from __future__ import annotations

import pytest
from pydantic import ValidationError

from tennis_genome.research_workbench.dynamic_state_benchmark import (
    DynamicStateShiftSpec,
    run_dynamic_state_shift_benchmark,
)


def _spec(**overrides: object) -> DynamicStateShiftSpec:
    payload: dict[str, object] = {
        "campaign_id": "dynamic-state-shift-001",
        "seeds": (1, 2, 3, 4, 5, 6, 7, 8),
        "pre_matches": 30,
        "layoff_days": 60,
        "post_matches": 30,
        "service_points_per_match": 60,
        "pre_shift_service_probability": 0.72,
        "post_shift_service_probability": 0.55,
    }
    payload.update(overrides)
    return DynamicStateShiftSpec(**payload)


def test_dynamic_state_shift_benchmark_is_deterministic_and_hash_bound() -> None:
    spec = _spec()
    first = run_dynamic_state_shift_benchmark(spec)
    second = run_dynamic_state_shift_benchmark(spec)

    assert first.semantic_sha256 == second.semantic_sha256
    assert first.campaign_spec_sha256 == spec.semantic_sha256
    assert first.n_seeds == len(spec.seeds)
    assert tuple(result.seed for result in first.results) == spec.seeds


def test_dynamic_state_reduces_stale_probability_error_after_planted_layoff_shift() -> None:
    report = run_dynamic_state_shift_benchmark(_spec())

    assert report.dynamic_joint_win_count >= 7
    assert report.dynamic_joint_win_rate >= 0.875
    assert report.mean_dynamic_mse < report.mean_fixed_mse
    assert (
        report.mean_dynamic_expected_log_loss
        < report.mean_fixed_expected_log_loss
    )


def test_dynamic_state_does_not_require_a_shift_to_avoid_material_instability() -> None:
    report = run_dynamic_state_shift_benchmark(
        _spec(
            campaign_id="dynamic-state-persistent-001",
            post_shift_service_probability=0.72,
        )
    )

    assert report.mean_dynamic_mse <= report.mean_fixed_mse + 0.0005
    assert (
        report.mean_dynamic_expected_log_loss
        <= report.mean_fixed_expected_log_loss + 0.001
    )


def test_shift_benchmark_spec_rejects_small_or_invalid_worlds() -> None:
    with pytest.raises(ValidationError, match="at least five seeds"):
        _spec(seeds=(1, 2, 3, 4))

    with pytest.raises(ValidationError, match="at least five matches"):
        _spec(pre_matches=4)

    with pytest.raises(ValidationError, match="layoff_days"):
        _spec(layoff_days=-1)

    with pytest.raises(ValidationError, match="service_points_per_match"):
        _spec(service_points_per_match=19)

    with pytest.raises(ValidationError, match="post_shift_service_probability"):
        _spec(post_shift_service_probability=1.0)


def test_report_keeps_each_seed_visible_instead_of_only_aggregating() -> None:
    report = run_dynamic_state_shift_benchmark(_spec())

    assert len(report.results) == report.n_seeds
    assert all(result.fixed_mse_to_true_probability >= 0.0 for result in report.results)
    assert all(result.dynamic_mse_to_true_probability >= 0.0 for result in report.results)
    assert all(
        isinstance(result.dynamic_wins_both, bool)
        for result in report.results
    )
