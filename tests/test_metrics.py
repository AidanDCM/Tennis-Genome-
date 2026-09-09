import pytest

from tennis_genome.evaluation.metrics import accuracy, binary_log_loss, brier_score


def test_perfect_predictions_have_zero_brier():
    assert brier_score([1, 0], [1.0, 0.0]) == pytest.approx(0.0)


def test_brier_penalizes_wrong_certainty():
    assert brier_score([1], [0.0]) == pytest.approx(1.0)


def test_log_loss_prefers_better_probability():
    better = binary_log_loss([1], [0.8])
    worse = binary_log_loss([1], [0.6])
    assert better < worse


def test_accuracy_is_secondary_threshold_metric():
    assert accuracy([1, 0, 1], [0.9, 0.4, 0.51]) == pytest.approx(1.0)
