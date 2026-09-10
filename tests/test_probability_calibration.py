import pytest

from tennis_genome.calibration.probability import (
    BetaCalibrator,
    IdentityCalibrator,
    IsotonicProbabilityCalibrator,
    PlattCalibrator,
    make_calibrator,
)


@pytest.mark.parametrize(
    "calibrator",
    [
        IdentityCalibrator(),
        PlattCalibrator(),
        BetaCalibrator(),
        IsotonicProbabilityCalibrator(),
    ],
)
def test_calibrators_fit_and_return_valid_probabilities(calibrator) -> None:
    probabilities = [0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9]
    outcomes = [False, False, False, True, False, True, True, True]

    calibrator.fit(probabilities, outcomes)
    calibrated = calibrator.predict([0.15, 0.5, 0.85])

    assert len(calibrated) == 3
    assert all(0.0 < probability < 1.0 for probability in calibrated)


def test_identity_preserves_interior_probabilities() -> None:
    calibrator = IdentityCalibrator().fit([0.2, 0.8], [False, True])
    assert calibrator.predict([0.2, 0.8]) == [0.2, 0.8]


def test_isotonic_is_monotonic() -> None:
    calibrator = IsotonicProbabilityCalibrator().fit(
        [0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9],
        [False, False, True, False, True, True, False, True],
    )
    calibrated = calibrator.predict([0.15, 0.25, 0.5, 0.75, 0.85])
    assert calibrated == sorted(calibrated)


def test_calibrators_reject_bad_fit_contract() -> None:
    with pytest.raises(ValueError, match="lengths must match"):
        PlattCalibrator().fit([0.2, 0.8], [True])
    with pytest.raises(ValueError, match="both outcome classes"):
        BetaCalibrator().fit([0.2, 0.8], [True, True])
    with pytest.raises(RuntimeError, match="not fitted"):
        IsotonicProbabilityCalibrator().predict([0.5])
    with pytest.raises(ValueError, match="unknown calibrator"):
        make_calibrator("magic")
