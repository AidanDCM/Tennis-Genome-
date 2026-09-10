from __future__ import annotations

import math
import random
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import product


@dataclass(frozen=True)
class PairedBootstrapResult:
    improvement: float
    lower: float
    upper: float
    confidence_level: float
    n_pairs: int
    n_resamples: int


@dataclass(frozen=True)
class PairedPermutationResult:
    improvement: float
    p_value: float
    n_pairs: int
    n_resamples: int | None
    exact: bool


@dataclass(frozen=True)
class McNemarResult:
    baseline_only_correct: int
    candidate_only_correct: int
    discordant_pairs: int
    p_value: float


def _as_float_list(values: Iterable[float], *, name: str) -> list[float]:
    result = [float(value) for value in values]
    if not result:
        raise ValueError(f"{name} must be non-empty")
    if any(not math.isfinite(value) for value in result):
        raise ValueError(f"{name} must contain only finite values")
    return result


def _paired_differences(
    baseline_losses: Iterable[float],
    candidate_losses: Iterable[float],
) -> list[float]:
    baseline = _as_float_list(baseline_losses, name="baseline_losses")
    candidate = _as_float_list(candidate_losses, name="candidate_losses")
    if len(baseline) != len(candidate):
        raise ValueError("baseline_losses and candidate_losses must have equal length")
    return [
        base - challenger
        for base, challenger in zip(baseline, candidate, strict=True)
    ]


def per_match_brier_losses(
    y_true: Iterable[int | bool],
    probabilities: Iterable[float],
) -> list[float]:
    ys = [1.0 if bool(value) else 0.0 for value in y_true]
    ps = [float(value) for value in probabilities]
    if len(ys) != len(ps) or not ys:
        raise ValueError("y_true and probabilities must have equal non-zero length")
    if any(not 0.0 <= probability <= 1.0 for probability in ps):
        raise ValueError("probabilities must be in [0, 1]")
    return [
        (probability - outcome) ** 2
        for outcome, probability in zip(ys, ps, strict=True)
    ]


def per_match_log_losses(
    y_true: Iterable[int | bool],
    probabilities: Iterable[float],
    *,
    epsilon: float = 1e-15,
) -> list[float]:
    if not 0.0 < epsilon < 0.5:
        raise ValueError("epsilon must be in (0, 0.5)")
    ys = [1.0 if bool(value) else 0.0 for value in y_true]
    ps = [float(value) for value in probabilities]
    if len(ys) != len(ps) or not ys:
        raise ValueError("y_true and probabilities must have equal non-zero length")
    if any(not 0.0 <= probability <= 1.0 for probability in ps):
        raise ValueError("probabilities must be in [0, 1]")

    losses: list[float] = []
    for outcome, probability in zip(ys, ps, strict=True):
        clipped = min(max(probability, epsilon), 1.0 - epsilon)
        losses.append(
            -(outcome * math.log(clipped) + (1.0 - outcome) * math.log(1.0 - clipped))
        )
    return losses


def _percentile(sorted_values: list[float], quantile: float) -> float:
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be in [0, 1]")
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = quantile * (len(sorted_values) - 1)
    lower_index = int(math.floor(position))
    upper_index = int(math.ceil(position))
    if lower_index == upper_index:
        return sorted_values[lower_index]
    fraction = position - lower_index
    return (
        sorted_values[lower_index] * (1.0 - fraction)
        + sorted_values[upper_index] * fraction
    )


def paired_bootstrap_improvement(
    baseline_losses: Iterable[float],
    candidate_losses: Iterable[float],
    *,
    confidence_level: float = 0.95,
    n_resamples: int = 10_000,
    seed: int = 0,
) -> PairedBootstrapResult:
    """Percentile paired bootstrap for mean loss improvement.

    Positive improvement means the candidate has lower loss than the baseline.
    Resampling is by matched observation, preserving the paired comparison.
    """

    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be in (0, 1)")
    if n_resamples <= 0:
        raise ValueError("n_resamples must be positive")

    differences = _paired_differences(baseline_losses, candidate_losses)
    n_pairs = len(differences)
    observed = sum(differences) / n_pairs
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(n_resamples):
        total = 0.0
        for _ in range(n_pairs):
            total += differences[rng.randrange(n_pairs)]
        draws.append(total / n_pairs)
    draws.sort()

    alpha = 1.0 - confidence_level
    return PairedBootstrapResult(
        improvement=observed,
        lower=_percentile(draws, alpha / 2.0),
        upper=_percentile(draws, 1.0 - alpha / 2.0),
        confidence_level=confidence_level,
        n_pairs=n_pairs,
        n_resamples=n_resamples,
    )


def paired_sign_flip_test(
    baseline_losses: Iterable[float],
    candidate_losses: Iterable[float],
    *,
    exact_max_pairs: int = 18,
    n_resamples: int = 20_000,
    seed: int = 0,
) -> PairedPermutationResult:
    """Two-sided paired randomization test for mean loss improvement.

    Under the sharp null, each matched loss difference may have its sign flipped.
    Small samples are enumerated exactly; larger samples use deterministic Monte Carlo.
    """

    if exact_max_pairs < 0:
        raise ValueError("exact_max_pairs must be non-negative")
    if n_resamples <= 0:
        raise ValueError("n_resamples must be positive")

    differences = _paired_differences(baseline_losses, candidate_losses)
    n_pairs = len(differences)
    observed = sum(differences) / n_pairs
    threshold = abs(observed) - 1e-15

    if n_pairs <= exact_max_pairs:
        extreme = 0
        total = 0
        for signs in product((-1.0, 1.0), repeat=n_pairs):
            statistic = sum(
                sign * difference
                for sign, difference in zip(signs, differences, strict=True)
            ) / n_pairs
            total += 1
            if abs(statistic) >= threshold:
                extreme += 1
        return PairedPermutationResult(
            improvement=observed,
            p_value=extreme / total,
            n_pairs=n_pairs,
            n_resamples=None,
            exact=True,
        )

    rng = random.Random(seed)
    extreme = 0
    for _ in range(n_resamples):
        statistic = sum(
            difference if rng.random() < 0.5 else -difference
            for difference in differences
        ) / n_pairs
        if abs(statistic) >= threshold:
            extreme += 1
    return PairedPermutationResult(
        improvement=observed,
        p_value=(extreme + 1) / (n_resamples + 1),
        n_pairs=n_pairs,
        n_resamples=n_resamples,
        exact=False,
    )


def _two_sided_binomial_half_probability(successes: int, trials: int) -> float:
    if trials == 0:
        return 1.0
    tail = sum(math.comb(trials, index) for index in range(successes + 1)) / (2**trials)
    return min(1.0, 2.0 * tail)


def mcnemar_exact(
    y_true: Iterable[int | bool],
    baseline_probabilities: Iterable[float],
    candidate_probabilities: Iterable[float],
    *,
    threshold: float = 0.5,
) -> McNemarResult:
    """Exact two-sided McNemar test for paired classification disagreements."""

    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be in [0, 1]")
    outcomes = [bool(value) for value in y_true]
    baseline = [float(value) for value in baseline_probabilities]
    candidate = [float(value) for value in candidate_probabilities]
    if not outcomes or len(outcomes) != len(baseline) or len(outcomes) != len(candidate):
        raise ValueError("all inputs must have equal non-zero length")
    if any(not 0.0 <= probability <= 1.0 for probability in baseline + candidate):
        raise ValueError("probabilities must be in [0, 1]")

    baseline_only = 0
    candidate_only = 0
    for outcome, base_probability, candidate_probability in zip(
        outcomes,
        baseline,
        candidate,
        strict=True,
    ):
        baseline_correct = (base_probability >= threshold) == outcome
        candidate_correct = (candidate_probability >= threshold) == outcome
        if baseline_correct and not candidate_correct:
            baseline_only += 1
        elif candidate_correct and not baseline_correct:
            candidate_only += 1

    discordant = baseline_only + candidate_only
    smaller = min(baseline_only, candidate_only)
    return McNemarResult(
        baseline_only_correct=baseline_only,
        candidate_only_correct=candidate_only,
        discordant_pairs=discordant,
        p_value=_two_sided_binomial_half_probability(smaller, discordant),
    )
