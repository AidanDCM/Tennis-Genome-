import pytest

from tennis_genome.evaluation.metrics import (
    accuracy,
    binary_log_loss,
    brier_score,
    calibration_bins,
    expected_calibration_error,
)


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


def test_calibration_bins_report_mean_probability_and_observed_rate():
    bins = calibration_bins([0, 1, 1, 0], [0.1, 0.2, 0.8, 0.9], n_bins=2)
    assert len(bins) == 2
    assert bins[0].n == 2
    assert bins[0].mean_probability == pytest.approx(0.15)
    assert bins[0].observed_rate == pytest.approx(0.5)
    assert bins[1].n == 2
    assert bins[1].mean_probability == pytest.approx(0.85)
    assert bins[1].observed_rate == pytest.approx(0.5)


def test_expected_calibration_error_is_zero_when_bins_are_perfectly_calibrated():
    y_true = [0, 1, 0, 1]
    probabilities = [0.5, 0.5, 0.5, 0.5]
    assert expected_calibration_error(y_true, probabilities, n_bins=10) == pytest.approx(0.0)


def test_expected_calibration_error_penalizes_miscalibration():
    y_true = [0, 0, 0, 0]
    probabilities = [0.9, 0.9, 0.9, 0.9]
    assert expected_calibration_error(y_true, probabilities, n_bins=10) == pytest.approx(0.9)
