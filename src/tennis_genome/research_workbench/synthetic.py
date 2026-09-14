from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class SyntheticWorld:
    """Known-truth benchmark world for research-process testing."""

    name: str
    seed: int
    feature_names: tuple[str, ...]
    features: NDArray[np.float64]
    baseline_probability: NDArray[np.float64]
    true_probability: NDArray[np.float64]
    outcomes: NDArray[np.int_]

    def __post_init__(self) -> None:
        n = self.outcomes.shape[0]
        if self.features.shape != (n, len(self.feature_names)):
            raise ValueError("feature matrix shape does not match feature names/outcomes")
        if self.baseline_probability.shape != (n,) or self.true_probability.shape != (n,):
            raise ValueError("probability vectors must align with outcomes")
        for array in (
            self.features,
            self.baseline_probability,
            self.true_probability,
            self.outcomes,
        ):
            array.setflags(write=False)


def _sigmoid(values: NDArray[np.float64]) -> NDArray[np.float64]:
    return 1.0 / (1.0 + np.exp(-values))


def null_world(*, n: int = 4000, seed: int = 20260913) -> SyntheticWorld:
    """World where the baseline is the true conditional probability."""

    if n <= 0:
        raise ValueError("n must be positive")
    rng = np.random.default_rng(seed)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    noise_feature = rng.normal(size=n)
    baseline = _sigmoid(0.55 * x1 - 0.35 * x2)
    outcomes = rng.binomial(1, baseline, size=n).astype(int)
    features = np.column_stack((x1, x2, noise_feature)).astype(float)
    return SyntheticWorld(
        name="null_oracle_baseline",
        seed=seed,
        feature_names=("x1", "x2", "noise_feature"),
        features=features,
        baseline_probability=baseline.copy(),
        true_probability=baseline.copy(),
        outcomes=outcomes,
    )


def miscalibration_world(*, n: int = 4000, seed: int = 20260913) -> SyntheticWorld:
    """World where the baseline has global calibration error but no special subgroup rule."""

    if n <= 0:
        raise ValueError("n must be positive")
    rng = np.random.default_rng(seed)
    state = rng.normal(size=n)
    distractor = rng.normal(size=n)
    true_probability = _sigmoid(1.15 * state)
    baseline = _sigmoid(0.70 * state)
    outcomes = rng.binomial(1, true_probability, size=n).astype(int)
    features = np.column_stack((state, distractor)).astype(float)
    return SyntheticWorld(
        name="global_miscalibration",
        seed=seed,
        feature_names=("state", "distractor"),
        features=features,
        baseline_probability=baseline,
        true_probability=true_probability,
        outcomes=outcomes,
    )


def interaction_world(
    *,
    n: int = 4000,
    seed: int = 20260913,
    interaction_effect: float = 0.9,
) -> SyntheticWorld:
    """World with a planted residual interaction absent from the baseline."""

    if n <= 0:
        raise ValueError("n must be positive")
    if interaction_effect == 0.0:
        raise ValueError("interaction_effect must be non-zero")
    rng = np.random.default_rng(seed)
    anchor = rng.normal(size=n)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    baseline_logit = 0.55 * anchor
    true_logit = baseline_logit + interaction_effect * x1 * x2
    baseline = _sigmoid(baseline_logit)
    true_probability = _sigmoid(true_logit)
    outcomes = rng.binomial(1, true_probability, size=n).astype(int)
    features = np.column_stack((anchor, x1, x2)).astype(float)
    return SyntheticWorld(
        name="planted_interaction",
        seed=seed,
        feature_names=("anchor", "x1", "x2"),
        features=features,
        baseline_probability=baseline,
        true_probability=true_probability,
        outcomes=outcomes,
    )
