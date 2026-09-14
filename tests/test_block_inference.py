from __future__ import annotations

import pytest

from tennis_genome.evaluation.block_inference import (
    paired_block_bootstrap_improvement,
    paired_block_sign_flip_test,
)


def test_block_bootstrap_preserves_registered_block_unit_and_is_reproducible() -> None:
    baseline = [0.40, 0.35, 0.30, 0.25, 0.20, 0.15]
    candidate = [0.30, 0.25, 0.32, 0.27, 0.18, 0.13]
    blocks = ["week-1", "week-1", "week-2", "week-2", "week-3", "week-3"]

    first = paired_block_bootstrap_improvement(
        baseline,
        candidate,
        blocks,
        n_resamples=2_000,
        seed=17,
    )
    second = paired_block_bootstrap_improvement(
        baseline,
        candidate,
        blocks,
        n_resamples=2_000,
        seed=17,
    )

    assert first == second
    assert first.n_pairs == 6
    assert first.n_blocks == 3
    assert first.improvement == pytest.approx((0.10 + 0.10 - 0.02 - 0.02 + 0.02 + 0.02) / 6)
    assert first.lower <= first.improvement <= first.upper


def test_block_bootstrap_rejects_single_block_or_misaligned_block_ids() -> None:
    with pytest.raises(ValueError, match="same length"):
        paired_block_bootstrap_improvement(
            [0.2, 0.3],
            [0.1, 0.2],
            ["one"],
        )

    with pytest.raises(ValueError, match="at least two blocks"):
        paired_block_bootstrap_improvement(
            [0.2, 0.3],
            [0.1, 0.2],
            ["same", "same"],
        )


def test_block_sign_flip_is_exact_at_small_block_count() -> None:
    result = paired_block_sign_flip_test(
        baseline_losses=[0.5, 0.4, 0.3, 0.2],
        candidate_losses=[0.3, 0.3, 0.25, 0.25],
        block_ids=["event-a", "event-a", "event-b", "event-b"],
        exact_max_blocks=2,
    )

    assert result.exact is True
    assert result.n_resamples is None
    assert result.n_pairs == 4
    assert result.n_blocks == 2
    assert 0.0 <= result.p_value <= 1.0


def test_block_sign_flip_uses_monte_carlo_above_exact_limit() -> None:
    result = paired_block_sign_flip_test(
        baseline_losses=[0.5, 0.4, 0.3, 0.2],
        candidate_losses=[0.3, 0.3, 0.25, 0.25],
        block_ids=["a", "b", "c", "d"],
        exact_max_blocks=2,
        n_resamples=1_000,
        seed=91,
    )

    assert result.exact is False
    assert result.n_resamples == 1_000
    assert result.n_blocks == 4
    assert 0.0 < result.p_value <= 1.0


def test_block_inference_rejects_nonfinite_losses_and_unhashable_ids() -> None:
    with pytest.raises(ValueError, match="finite"):
        paired_block_bootstrap_improvement(
            [0.2, float("nan")],
            [0.1, 0.2],
            ["a", "b"],
        )

    with pytest.raises(ValueError, match="hashable"):
        paired_block_bootstrap_improvement(
            [0.2, 0.3],
            [0.1, 0.2],
            [["a"], ["b"]],  # type: ignore[list-item]
        )


def test_block_definition_changes_uncertainty_without_changing_observed_improvement() -> None:
    baseline = [0.5, 0.5, 0.2, 0.2, 0.4, 0.4]
    candidate = [0.3, 0.3, 0.3, 0.3, 0.35, 0.35]

    weekly = paired_block_bootstrap_improvement(
        baseline,
        candidate,
        ["w1", "w1", "w2", "w2", "w3", "w3"],
        n_resamples=2_000,
        seed=4,
    )
    event = paired_block_bootstrap_improvement(
        baseline,
        candidate,
        ["e1", "e2", "e3", "e4", "e5", "e6"],
        n_resamples=2_000,
        seed=4,
    )

    assert weekly.improvement == pytest.approx(event.improvement)
    assert weekly.n_blocks == 3
    assert event.n_blocks == 6
    assert (weekly.lower, weekly.upper) != (event.lower, event.upper)
