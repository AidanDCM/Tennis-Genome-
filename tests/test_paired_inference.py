from __future__ import annotations

import math

import pytest

from tennis_genome.evaluation.paired_inference import (
    mcnemar_exact,
    paired_bootstrap_improvement,
    paired_sign_flip_test,
    per_match_brier_losses,
    per_match_log_losses,
)


def test_per_match_losses_match_expected_values() -> None:
    outcomes = [1, 0]
    probabilities = [0.8, 0.3]

    brier = per_match_brier_losses(outcomes, probabilities)
    log_losses = per_match_log_losses(outcomes, probabilities)

    assert brier == pytest.approx([0.04, 0.09])
    assert log_losses == pytest.approx([-math.log(0.8), -math.log(0.7)])


def test_paired_bootstrap_reports_positive_candidate_improvement() -> None:
    baseline = [0.25] * 12
    candidate = [0.04] * 12

    result = paired_bootstrap_improvement(
        baseline,
        candidate,
        n_resamples=500,
        seed=7,
    )

    assert result.improvement == pytest.approx(0.21)
    assert result.lower == pytest.approx(0.21)
    assert result.upper == pytest.approx(0.21)
    assert result.n_pairs == 12


def test_exact_sign_flip_detects_consistent_improvement() -> None:
    baseline = [0.30] * 10
    candidate = [0.20] * 10

    result = paired_sign_flip_test(baseline, candidate, exact_max_pairs=12)

    assert result.exact is True
    assert result.n_resamples is None
    assert result.improvement == pytest.approx(0.10)
    assert result.p_value == pytest.approx(2 / (2**10))


def test_mcnemar_exact_uses_only_discordant_pairs() -> None:
    outcomes = [1, 1, 1, 1, 0, 0]
    baseline = [0.4, 0.4, 0.4, 0.4, 0.2, 0.2]
    candidate = [0.8, 0.8, 0.8, 0.8, 0.2, 0.2]

    result = mcnemar_exact(outcomes, baseline, candidate)

    assert result.baseline_only_correct == 0
    assert result.candidate_only_correct == 4
    assert result.discordant_pairs == 4
    assert result.p_value == pytest.approx(0.125)


def test_paired_inference_rejects_misaligned_inputs() -> None:
    with pytest.raises(ValueError, match="equal length"):
        paired_bootstrap_improvement([0.2, 0.3], [0.1])

    with pytest.raises(ValueError, match="equal non-zero length"):
        mcnemar_exact([1], [0.7], [0.8, 0.9])
