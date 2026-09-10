from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from math import log

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

_EPSILON = 1e-6


def _clip_probability(value: float) -> float:
    return min(max(float(value), _EPSILON), 1.0 - _EPSILON)


def _validate_fit_data(
    probabilities: Iterable[float],
    outcomes: Iterable[bool],
) -> tuple[list[float], list[int]]:
    probs = [_clip_probability(value) for value in probabilities]
    labels = [int(bool(value)) for value in outcomes]
    if len(probs) != len(labels):
        raise ValueError("probability and outcome lengths must match")
    if not probs:
        raise ValueError("calibration data is empty")
    if len(set(labels)) < 2:
        raise ValueError("calibration data must contain both outcome classes")
    return probs, labels


class ProbabilityCalibrator(ABC):
    """Minimal interface for post-hoc probability calibration."""

    @abstractmethod
    def fit(
        self,
        probabilities: Iterable[float],
        outcomes: Iterable[bool],
    ) -> ProbabilityCalibrator:
        raise NotImplementedError

    @abstractmethod
    def predict(self, probabilities: Iterable[float]) -> list[float]:
        raise NotImplementedError


class IdentityCalibrator(ProbabilityCalibrator):
    """Control calibrator that returns probabilities unchanged."""

    def fit(
        self,
        probabilities: Iterable[float],
        outcomes: Iterable[bool],
    ) -> IdentityCalibrator:
        _validate_fit_data(probabilities, outcomes)
        return self

    def predict(self, probabilities: Iterable[float]) -> list[float]:
        return [_clip_probability(value) for value in probabilities]


class PlattCalibrator(ProbabilityCalibrator):
    """Logistic calibration on the logit of the raw probability."""

    def __init__(self) -> None:
        self._model: LogisticRegression | None = None

    @staticmethod
    def _features(probabilities: Iterable[float]) -> list[list[float]]:
        return [
            [log(probability / (1.0 - probability))]
            for probability in (_clip_probability(value) for value in probabilities)
        ]

    def fit(
        self,
        probabilities: Iterable[float],
        outcomes: Iterable[bool],
    ) -> PlattCalibrator:
        probs, labels = _validate_fit_data(probabilities, outcomes)
        model = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
        model.fit(self._features(probs), labels)
        self._model = model
        return self

    def predict(self, probabilities: Iterable[float]) -> list[float]:
        if self._model is None:
            raise RuntimeError("calibrator is not fitted")
        probs = [_clip_probability(value) for value in probabilities]
        if not probs:
            return []
        return self._model.predict_proba(self._features(probs))[:, 1].tolist()


class BetaCalibrator(ProbabilityCalibrator):
    """Beta-style logistic calibration using log(p) and -log(1-p)."""

    def __init__(self) -> None:
        self._model: LogisticRegression | None = None

    @staticmethod
    def _features(probabilities: Iterable[float]) -> list[list[float]]:
        return [
            [log(probability), -log(1.0 - probability)]
            for probability in (_clip_probability(value) for value in probabilities)
        ]

    def fit(
        self,
        probabilities: Iterable[float],
        outcomes: Iterable[bool],
    ) -> BetaCalibrator:
        probs, labels = _validate_fit_data(probabilities, outcomes)
        model = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
        model.fit(self._features(probs), labels)
        self._model = model
        return self

    def predict(self, probabilities: Iterable[float]) -> list[float]:
        if self._model is None:
            raise RuntimeError("calibrator is not fitted")
        probs = [_clip_probability(value) for value in probabilities]
        if not probs:
            return []
        return self._model.predict_proba(self._features(probs))[:, 1].tolist()


class IsotonicProbabilityCalibrator(ProbabilityCalibrator):
    """Monotonic non-parametric probability calibration."""

    def __init__(self) -> None:
        self._model: IsotonicRegression | None = None

    def fit(
        self,
        probabilities: Iterable[float],
        outcomes: Iterable[bool],
    ) -> IsotonicProbabilityCalibrator:
        probs, labels = _validate_fit_data(probabilities, outcomes)
        model = IsotonicRegression(
            y_min=_EPSILON,
            y_max=1.0 - _EPSILON,
            out_of_bounds="clip",
        )
        model.fit(np.asarray(probs), np.asarray(labels))
        self._model = model
        return self

    def predict(self, probabilities: Iterable[float]) -> list[float]:
        if self._model is None:
            raise RuntimeError("calibrator is not fitted")
        probs = [_clip_probability(value) for value in probabilities]
        if not probs:
            return []
        return self._model.predict(np.asarray(probs)).astype(float).tolist()


def make_calibrator(name: str) -> ProbabilityCalibrator:
    normalized = name.strip().casefold()
    if normalized == "identity":
        return IdentityCalibrator()
    if normalized == "platt":
        return PlattCalibrator()
    if normalized == "beta":
        return BetaCalibrator()
    if normalized == "isotonic":
        return IsotonicProbabilityCalibrator()
    raise ValueError(f"unknown calibrator: {name}")
