from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Iterable

from .metrics import (
    accuracy,
    binary_log_loss,
    brier_score,
    calibration_bins,
    confidence_from_probability,
    expected_calibration_error,
)

_NEUTRAL_BRIER = 0.25
_NEUTRAL_LOG_LOSS = math.log(2.0)
_DEFAULT_COVERAGES = (1.0, 0.9, 0.75, 0.5, 0.25, 0.1)
_CONFIDENCE_EDGES = (0.50, 0.55, 0.60, 0.65, 0.70, 0.80, 1.0000000001)


def _probability(value: float, *, field_name: str) -> float:
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{field_name} must be finite in [0, 1]")
    return value


def _finite(value: float, *, field_name: str) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{field_name} must be finite")
    return value


@dataclass(frozen=True)
class ValidationObservation:
    """One outcome-linked prediction with pre-match-only diagnostic context."""

    model_id: str
    match_id: str
    probability_a: float
    outcome_a_won: bool
    event_date: date | None = None
    component_probabilities: dict[str, float] = field(default_factory=dict)
    pre_match_diagnostics: dict[str, float | int | bool | None] = field(
        default_factory=dict
    )
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.model_id.strip() or not self.match_id.strip():
            raise ValueError("model_id and match_id must be nonblank")
        object.__setattr__(
            self,
            "probability_a",
            _probability(self.probability_a, field_name="probability_a"),
        )
        components: dict[str, float] = {}
        for name, raw in self.component_probabilities.items():
            if not str(name).strip():
                raise ValueError("component probability names must be nonblank")
            components[str(name)] = _probability(
                float(raw),
                field_name=f"component_probabilities[{name}]",
            )
        object.__setattr__(self, "component_probabilities", components)
        if len(self.tags) != len(set(self.tags)):
            raise ValueError("tags must be unique")
        object.__setattr__(self, "tags", tuple(sorted(self.tags)))

    @property
    def confidence(self) -> float:
        return confidence_from_probability(self.probability_a)

    @property
    def predicted_a(self) -> bool:
        return self.probability_a >= 0.5

    @property
    def correct(self) -> bool:
        return self.predicted_a == self.outcome_a_won

    @property
    def brier(self) -> float:
        target = 1.0 if self.outcome_a_won else 0.0
        return (self.probability_a - target) ** 2

    @property
    def log_loss(self) -> float:
        return binary_log_loss([self.outcome_a_won], [self.probability_a])


@dataclass(frozen=True)
class CalibrationFit:
    intercept: float
    slope: float



def _binary_auc(labels: list[bool], scores: list[float]) -> float | None:
    """Tie-aware ROC AUC without external dependencies."""

    if len(labels) != len(scores) or not labels:
        raise ValueError("AUC labels and scores must have equal non-zero length")
    positives = sum(int(value) for value in labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None

    ordered = sorted(
        enumerate(scores),
        key=lambda item: (item[1], item[0]),
    )
    ranks = [0.0] * len(scores)
    cursor = 0
    while cursor < len(ordered):
        stop = cursor + 1
        while stop < len(ordered) and ordered[stop][1] == ordered[cursor][1]:
            stop += 1
        average_rank = ((cursor + 1) + stop) / 2.0
        for index in range(cursor, stop):
            ranks[ordered[index][0]] = average_rank
        cursor = stop

    positive_rank_sum = sum(
        rank for rank, label in zip(ranks, labels, strict=True) if label
    )
    return (
        positive_rank_sum - positives * (positives + 1) / 2.0
    ) / (positives * negatives)


def _calibration_fit(
    y_true: list[bool],
    probabilities: list[float],
) -> CalibrationFit | None:
    """Logistic calibration fit: outcome ~ intercept + slope * logit(p).

    This is diagnostic only. Degenerate samples return None rather than inventing
    a calibration slope/intercept.
    """

    if len(y_true) != len(probabilities) or len(y_true) < 3:
        return None
    if len(set(y_true)) < 2:
        return None
    epsilon = 1e-9
    xs = []
    for raw in probabilities:
        p = min(max(float(raw), epsilon), 1.0 - epsilon)
        xs.append(math.log(p / (1.0 - p)))
    mean_x = sum(xs) / len(xs)
    if max(abs(x - mean_x) for x in xs) < 1e-12:
        return None

    intercept = 0.0
    slope = 1.0
    for _ in range(100):
        g0 = 0.0
        g1 = 0.0
        h00 = 0.0
        h01 = 0.0
        h11 = 0.0
        for y, x in zip(y_true, xs, strict=True):
            z = max(min(intercept + slope * x, 35.0), -35.0)
            mu = 1.0 / (1.0 + math.exp(-z))
            residual = (1.0 if y else 0.0) - mu
            weight = max(mu * (1.0 - mu), 1e-12)
            g0 += residual
            g1 += residual * x
            h00 += weight
            h01 += weight * x
            h11 += weight * x * x
        determinant = h00 * h11 - h01 * h01
        if determinant <= 1e-15:
            return None
        delta_intercept = (g0 * h11 - g1 * h01) / determinant
        delta_slope = (g1 * h00 - g0 * h01) / determinant
        intercept += delta_intercept
        slope += delta_slope
        if max(abs(delta_intercept), abs(delta_slope)) < 1e-9:
            break
    if not math.isfinite(intercept) or not math.isfinite(slope):
        return None
    return CalibrationFit(intercept=intercept, slope=slope)


def _wilson_interval(successes: int, n: int, *, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0 or successes < 0 or successes > n:
        raise ValueError("Wilson interval requires 0 <= successes <= n and n > 0")
    p = successes / n
    denominator = 1.0 + (z * z / n)
    center = (p + z * z / (2.0 * n)) / denominator
    radius = (
        z
        * math.sqrt((p * (1.0 - p) / n) + z * z / (4.0 * n * n))
        / denominator
    )
    return max(0.0, center - radius), min(1.0, center + radius)


def _maximum_calibration_error(y_true: list[bool], probabilities: list[float], n_bins: int) -> float:
    buckets = calibration_bins(y_true, probabilities, n_bins=n_bins)
    return max(
        abs(bucket.mean_probability - bucket.observed_rate)
        for bucket in buckets
    )


def _summary(observations: list[ValidationObservation], *, n_bins: int) -> dict[str, Any]:
    if not observations:
        raise ValueError("validation summary requires observations")
    outcomes = [row.outcome_a_won for row in observations]
    probabilities = [row.probability_a for row in observations]
    correct_count = sum(int(row.correct) for row in observations)
    acc = accuracy(outcomes, probabilities)
    brier = brier_score(outcomes, probabilities)
    log_loss = binary_log_loss(outcomes, probabilities)
    ci_low, ci_high = _wilson_interval(correct_count, len(observations))
    fit = _calibration_fit(outcomes, probabilities)
    high_65 = [row for row in observations if max(row.probability_a, 1.0 - row.probability_a) >= 0.65]
    high_75 = [row for row in observations if max(row.probability_a, 1.0 - row.probability_a) >= 0.75]

    return {
        "n": len(observations),
        "accuracy": acc,
        "accuracy_correct_count": correct_count,
        "accuracy_wilson_95_low": ci_low,
        "accuracy_wilson_95_high": ci_high,
        "brier": brier,
        "brier_skill_vs_50": 1.0 - (brier / _NEUTRAL_BRIER),
        "log_loss": log_loss,
        "log_loss_skill_vs_50": 1.0 - (log_loss / _NEUTRAL_LOG_LOSS),
        "expected_calibration_error": expected_calibration_error(
            outcomes,
            probabilities,
            n_bins=n_bins,
        ),
        "maximum_calibration_error": _maximum_calibration_error(
            outcomes,
            probabilities,
            n_bins,
        ),
        "calibration_intercept": None if fit is None else fit.intercept,
        "calibration_slope": None if fit is None else fit.slope,
        "mean_probability_a": sum(probabilities) / len(probabilities),
        "observed_rate_a": sum(int(value) for value in outcomes) / len(outcomes),
        "mean_confidence": sum(row.confidence for row in observations) / len(observations),
        "confidence_correctness_auc": _binary_auc(
            [row.correct for row in observations],
            [row.confidence for row in observations],
        ),
        "high_confidence_65_count": len(high_65),
        "high_confidence_65_miss_count": sum(int(not row.correct) for row in high_65),
        "high_confidence_65_miss_rate": (
            None
            if not high_65
            else sum(int(not row.correct) for row in high_65) / len(high_65)
        ),
        "high_confidence_75_count": len(high_75),
        "high_confidence_75_miss_count": sum(int(not row.correct) for row in high_75),
        "high_confidence_75_miss_rate": (
            None
            if not high_75
            else sum(int(not row.correct) for row in high_75) / len(high_75)
        ),
    }


def _reliability_table(
    observations: list[ValidationObservation],
    *,
    n_bins: int,
) -> list[dict[str, Any]]:
    outcomes = [row.outcome_a_won for row in observations]
    probabilities = [row.probability_a for row in observations]
    return [asdict(bucket) for bucket in calibration_bins(outcomes, probabilities, n_bins=n_bins)]


def _confidence_buckets(observations: list[ValidationObservation]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for lower, upper in zip(_CONFIDENCE_EDGES[:-1], _CONFIDENCE_EDGES[1:], strict=True):
        rows = [
            row
            for row in observations
            if lower
            <= max(row.probability_a, 1.0 - row.probability_a)
            < upper
        ]
        if not rows:
            continue
        result.append(
            {
                "lower_predicted_winner_probability": lower,
                "upper_predicted_winner_probability": min(upper, 1.0),
                "n": len(rows),
                "mean_predicted_winner_probability": sum(
                    max(row.probability_a, 1.0 - row.probability_a) for row in rows
                )
                / len(rows),
                "accuracy": sum(int(row.correct) for row in rows) / len(rows),
                "mean_brier": sum(row.brier for row in rows) / len(rows),
                "mean_log_loss": sum(row.log_loss for row in rows) / len(rows),
            }
        )
    return result


def _selective_curve(
    observations: list[ValidationObservation],
    *,
    n_bins: int,
    coverages: tuple[float, ...],
) -> list[dict[str, Any]]:
    ordered = sorted(
        observations,
        key=lambda row: (-row.confidence, row.match_id),
    )
    result: list[dict[str, Any]] = []
    for coverage in coverages:
        if not 0.0 < coverage <= 1.0:
            raise ValueError("selective coverage targets must be in (0, 1]")
        retained_n = max(1, math.ceil(len(ordered) * coverage))
        rows = ordered[:retained_n]
        summary = _summary(rows, n_bins=n_bins)
        result.append(
            {
                "target_coverage": coverage,
                "retained_n": retained_n,
                "actual_coverage": retained_n / len(ordered),
                "minimum_retained_confidence": min(row.confidence for row in rows),
                "accuracy": summary["accuracy"],
                "brier": summary["brier"],
                "log_loss": summary["log_loss"],
                "expected_calibration_error": summary["expected_calibration_error"],
            }
        )
    return result


def _tag_slices(
    observations: list[ValidationObservation],
    *,
    n_bins: int,
) -> list[dict[str, Any]]:
    tags = sorted({tag for row in observations for tag in row.tags})
    result = []
    for tag in tags:
        rows = [row for row in observations if tag in row.tags]
        summary = _summary(rows, n_bins=n_bins)
        result.append({"tag": tag, **summary})
    return result


def _monthly_slices(
    observations: list[ValidationObservation],
    *,
    n_bins: int,
) -> list[dict[str, Any]]:
    months = sorted(
        {
            row.event_date.strftime("%Y-%m")
            for row in observations
            if row.event_date is not None
        }
    )
    result = []
    for month in months:
        rows = [
            row
            for row in observations
            if row.event_date is not None and row.event_date.strftime("%Y-%m") == month
        ]
        result.append({"month": month, **_summary(rows, n_bins=n_bins)})
    return result


def _component_disagreement(observations: list[ValidationObservation]) -> dict[str, Any]:
    rows: list[tuple[ValidationObservation, float]] = []
    for observation in observations:
        values = tuple(observation.component_probabilities.values())
        if len(values) < 2:
            continue
        rows.append((observation, max(values) - min(values)))
    if not rows:
        return {
            "n": 0,
            "mean_range": None,
            "max_range": None,
            "high_disagreement_10_count": 0,
            "high_disagreement_10_accuracy": None,
            "low_disagreement_accuracy": None,
        }
    high = [row for row, value in rows if value >= 0.10]
    low = [row for row, value in rows if value < 0.10]
    return {
        "n": len(rows),
        "mean_range": sum(value for _, value in rows) / len(rows),
        "max_range": max(value for _, value in rows),
        "high_disagreement_10_count": len(high),
        "high_disagreement_10_accuracy": (
            None if not high else sum(int(row.correct) for row in high) / len(high)
        ),
        "low_disagreement_accuracy": (
            None if not low else sum(int(row.correct) for row in low) / len(low)
        ),
    }


def build_validation_report(
    observations: Iterable[ValidationObservation],
    *,
    population_size: int | None = None,
    n_bins: int = 10,
    selective_coverages: tuple[float, ...] = _DEFAULT_COVERAGES,
) -> dict[str, Any]:
    rows = list(observations)
    if not rows:
        raise ValueError("validation report requires at least one observation")
    model_ids = {row.model_id for row in rows}
    if len(model_ids) != 1:
        raise ValueError("validation report requires exactly one model_id")
    match_ids = [row.match_id for row in rows]
    if len(match_ids) != len(set(match_ids)):
        raise ValueError("validation observations require unique match_id values")
    if n_bins <= 0:
        raise ValueError("n_bins must be positive")

    if population_size is None:
        population_size = len(rows)
    if population_size < len(rows):
        raise ValueError("population_size cannot be smaller than observation count")

    overall = _summary(rows, n_bins=n_bins)
    return {
        "schema_version": "tennis-genome-prediction-validation-report-v1",
        "model_id": next(iter(model_ids)),
        "population_size": population_size,
        "prediction_count": len(rows),
        "abstention_count": population_size - len(rows),
        "coverage": len(rows) / population_size,
        "overall": overall,
        "reliability_table": _reliability_table(rows, n_bins=n_bins),
        "confidence_buckets": _confidence_buckets(rows),
        "selective_coverage_curve": _selective_curve(
            rows,
            n_bins=n_bins,
            coverages=selective_coverages,
        ),
        "component_disagreement": _component_disagreement(rows),
        "tag_slices": _tag_slices(rows, n_bins=n_bins),
        "monthly_slices": _monthly_slices(rows, n_bins=n_bins),
    }


def build_paired_model_comparison(
    baseline: Iterable[ValidationObservation],
    candidate: Iterable[ValidationObservation],
    *,
    n_bins: int = 10,
) -> dict[str, Any]:
    baseline_rows = list(baseline)
    candidate_rows = list(candidate)
    if not baseline_rows or not candidate_rows:
        raise ValueError("paired comparison requires non-empty model observations")
    baseline_by_match = {row.match_id: row for row in baseline_rows}
    candidate_by_match = {row.match_id: row for row in candidate_rows}
    if len(baseline_by_match) != len(baseline_rows):
        raise ValueError("baseline contains duplicate match IDs")
    if len(candidate_by_match) != len(candidate_rows):
        raise ValueError("candidate contains duplicate match IDs")
    if set(baseline_by_match) != set(candidate_by_match):
        raise ValueError("paired comparison requires identical match populations")

    ordered_ids = sorted(baseline_by_match)
    base = [baseline_by_match[match_id] for match_id in ordered_ids]
    cand = [candidate_by_match[match_id] for match_id in ordered_ids]
    for left, right in zip(base, cand, strict=True):
        if left.outcome_a_won != right.outcome_a_won:
            raise ValueError("paired comparison outcome mismatch")
    base_summary = _summary(base, n_bins=n_bins)
    cand_summary = _summary(cand, n_bins=n_bins)

    brier_better = 0
    log_loss_better = 0
    accuracy_better = 0
    accuracy_worse = 0
    for left, right in zip(base, cand, strict=True):
        brier_better += int(right.brier < left.brier)
        log_loss_better += int(right.log_loss < left.log_loss)
        accuracy_better += int(right.correct and not left.correct)
        accuracy_worse += int(left.correct and not right.correct)

    return {
        "schema_version": "tennis-genome-paired-model-comparison-v1",
        "baseline_model_id": base[0].model_id,
        "candidate_model_id": cand[0].model_id,
        "n": len(base),
        "baseline": base_summary,
        "candidate": cand_summary,
        "delta_accuracy_candidate_minus_baseline": (
            cand_summary["accuracy"] - base_summary["accuracy"]
        ),
        "delta_brier_candidate_minus_baseline": (
            cand_summary["brier"] - base_summary["brier"]
        ),
        "delta_log_loss_candidate_minus_baseline": (
            cand_summary["log_loss"] - base_summary["log_loss"]
        ),
        "delta_ece_candidate_minus_baseline": (
            cand_summary["expected_calibration_error"]
            - base_summary["expected_calibration_error"]
        ),
        "fraction_matches_candidate_lower_brier": brier_better / len(base),
        "fraction_matches_candidate_lower_log_loss": log_loss_better / len(base),
        "candidate_only_correct_count": accuracy_better,
        "baseline_only_correct_count": accuracy_worse,
    }
