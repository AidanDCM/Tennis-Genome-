from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass


def _validate_probability(p: float) -> float:
    p = float(p)
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"probability must be in [0, 1], got {p}")
    return p


@dataclass(frozen=True)
class CalibrationBin:
    lower: float
    upper: float
    n: int
    mean_probability: float
    observed_rate: float


def brier_score(y_true: Iterable[int | bool], probabilities: Iterable[float]) -> float:
    """Mean squared probability error for binary outcomes."""
    ys = [1.0 if bool(y) else 0.0 for y in y_true]
    ps = [_validate_probability(p) for p in probabilities]
    if len(ys) != len(ps) or not ys:
        raise ValueError("y_true and probabilities must have equal non-zero length")
    return sum((p - y) ** 2 for y, p in zip(ys, ps, strict=True)) / len(ys)


def binary_log_loss(
    y_true: Iterable[int | bool],
    probabilities: Iterable[float],
    *,
    epsilon: float = 1e-15,
) -> float:
    """Binary log loss with numerical clipping only at evaluation time."""
    if not 0.0 < epsilon < 0.5:
        raise ValueError("epsilon must be in (0, 0.5)")
    ys = [1.0 if bool(y) else 0.0 for y in y_true]
    ps = [_validate_probability(p) for p in probabilities]
    if len(ys) != len(ps) or not ys:
        raise ValueError("y_true and probabilities must have equal non-zero length")
    total = 0.0
    for y, p in zip(ys, ps, strict=True):
        p = min(max(p, epsilon), 1.0 - epsilon)
        total += -(y * math.log(p) + (1.0 - y) * math.log(1.0 - p))
    return total / len(ys)


def accuracy(
    y_true: Iterable[int | bool],
    probabilities: Iterable[float],
    *,
    threshold: float = 0.5,
) -> float:
    """Binary accuracy; secondary to calibrated probability metrics."""
    ys = [bool(y) for y in y_true]
    ps = [_validate_probability(p) for p in probabilities]
    if len(ys) != len(ps) or not ys:
        raise ValueError("y_true and probabilities must have equal non-zero length")
    predictions = [p >= threshold for p in ps]
    return sum(pred == y for pred, y in zip(predictions, ys, strict=True)) / len(ys)


def calibration_bins(
    y_true: Iterable[int | bool],
    probabilities: Iterable[float],
    *,
    n_bins: int = 10,
) -> list[CalibrationBin]:
    """Return fixed-width calibration bins over [0, 1].

    Empty bins are omitted. Fixed boundaries make results comparable across
    model versions; quantile bins can be added later for diagnostic plots.
    """
    if n_bins <= 0:
        raise ValueError("n_bins must be positive")
    ys = [1.0 if bool(y) else 0.0 for y in y_true]
    ps = [_validate_probability(p) for p in probabilities]
    if len(ys) != len(ps) or not ys:
        raise ValueError("y_true and probabilities must have equal non-zero length")

    members: list[list[tuple[float, float]]] = [[] for _ in range(n_bins)]
    for y, p in zip(ys, ps, strict=True):
        index = min(int(p * n_bins), n_bins - 1)
        members[index].append((y, p))

    result: list[CalibrationBin] = []
    for index, rows in enumerate(members):
        if not rows:
            continue
        lower = index / n_bins
        upper = (index + 1) / n_bins
        result.append(
            CalibrationBin(
                lower=lower,
                upper=upper,
                n=len(rows),
                mean_probability=sum(p for _, p in rows) / len(rows),
                observed_rate=sum(y for y, _ in rows) / len(rows),
            )
        )
    return result


def expected_calibration_error(
    y_true: Iterable[int | bool],
    probabilities: Iterable[float],
    *,
    n_bins: int = 10,
) -> float:
    """Weighted absolute calibration gap across fixed-width bins.

    ECE is a useful summary diagnostic but is bin-dependent and should never
    replace Brier/log loss or the full reliability table.
    """
    ys = list(y_true)
    ps = list(probabilities)
    bins = calibration_bins(ys, ps, n_bins=n_bins)
    total = len(ys)
    return sum(
        (bucket.n / total) * abs(bucket.mean_probability - bucket.observed_rate)
        for bucket in bins
    )


def confidence_from_probability(p: float) -> float:
    """Naive distance-from-0.5 confidence baseline.

    This is intentionally simple and should be treated only as a baseline for
    testing richer uncertainty/disagreement/density-based confidence systems.
    """
    p = _validate_probability(p)
    return abs(p - 0.5) * 2.0
