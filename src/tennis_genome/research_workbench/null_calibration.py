from __future__ import annotations

import math
from typing import Literal

from pydantic import field_validator, model_validator

from .contracts import WorkbenchRecord
from .synthetic import null_world
from .synthetic_benchmark import SyntheticBenchmarkReport, run_synthetic_benchmark


class NullCalibrationSpec(WorkbenchRecord):
    """Frozen operating point for repeated known-null research-machine checks."""

    campaign_id: str
    seeds: tuple[int, ...]
    n_per_world: int
    source_code_sha: str
    brier_material_gain: float
    log_loss_material_gain: float
    max_false_promotion_rate: float
    confidence_level: float = 0.95

    @field_validator("campaign_id", "source_code_sha")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("null-calibration identifiers must be nonblank")
        return value

    @field_validator("seeds")
    @classmethod
    def _unique_seeds(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if len(value) < 5:
            raise ValueError("null calibration requires at least five registered seeds")
        if len(value) != len(set(value)):
            raise ValueError("null calibration seeds must be unique")
        return value

    @model_validator(mode="after")
    def _validate_operating_point(self) -> NullCalibrationSpec:
        if self.n_per_world < 500:
            raise ValueError("null calibration requires at least 500 rows per world")
        if self.brier_material_gain <= 0.0:
            raise ValueError("brier_material_gain must be positive")
        if self.log_loss_material_gain <= 0.0:
            raise ValueError("log_loss_material_gain must be positive")
        if not 0.0 <= self.max_false_promotion_rate < 1.0:
            raise ValueError("max_false_promotion_rate must be in [0, 1)")
        if not 0.0 < self.confidence_level < 1.0:
            raise ValueError("confidence_level must be in (0, 1)")
        return self


class NullSeedResult(WorkbenchRecord):
    seed: int
    calibration_brier_gain: float
    calibration_log_loss_gain: float
    interaction_brier_gain: float
    interaction_log_loss_gain: float
    calibration_false_promotion: bool
    interaction_false_promotion: bool
    any_false_promotion: bool


class NullCalibrationReport(WorkbenchRecord):
    """Empirical false-promotion audit across a preregistered family of null worlds."""

    campaign_spec_sha256: str
    campaign_id: str
    n_worlds: int
    n_false_promotions: int
    false_promotion_rate: float
    upper_confidence_bound: float
    max_allowed_false_promotion_rate: float
    status: Literal["HEALTHY", "FAILED"]
    results: tuple[NullSeedResult, ...]


def _gain(candidate: float, baseline: float) -> float:
    """Positive values mean the candidate improved the proper score."""

    return baseline - candidate


def _material_promotion(
    report: SyntheticBenchmarkReport,
    *,
    candidate: Literal["calibration", "interaction"],
    brier_gain: float,
    log_loss_gain: float,
) -> tuple[float, float, bool]:
    result = report.calibration if candidate == "calibration" else report.interaction
    observed_brier_gain = _gain(result.brier, report.baseline.brier)
    observed_log_loss_gain = _gain(result.log_loss, report.baseline.log_loss)
    promoted = (
        observed_brier_gain >= brier_gain
        and observed_log_loss_gain >= log_loss_gain
    )
    return observed_brier_gain, observed_log_loss_gain, promoted


def _wilson_upper_bound(
    *,
    successes: int,
    trials: int,
    confidence_level: float,
) -> float:
    """One-sided Wilson upper confidence bound for a binomial rate.

    The z value is obtained with Python's standard-library NormalDist so campaign
    calibration has no additional statistical dependency.
    """

    if trials <= 0:
        raise ValueError("trials must be positive")
    if not 0 <= successes <= trials:
        raise ValueError("successes must be between zero and trials")

    from statistics import NormalDist

    z = NormalDist().inv_cdf(confidence_level)
    p = successes / trials
    z2 = z * z
    denominator = 1.0 + z2 / trials
    center = p + z2 / (2.0 * trials)
    radius = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * trials)) / trials)
    return min(1.0, (center + radius) / denominator)


def run_null_calibration_campaign(spec: NullCalibrationSpec) -> NullCalibrationReport:
    """Run the real synthetic benchmark repeatedly when no improvement exists.

    A false promotion occurs only when a challenger clears both preregistered material
    proper-score thresholds against the oracle baseline in the same null world.

    Campaign health is intentionally judged by the upper confidence bound, not only by
    the observed false-promotion fraction. Small campaigns therefore cannot certify an
    aggressive false-promotion ceiling merely because they happened to observe zero.
    """

    results: list[NullSeedResult] = []
    for seed in spec.seeds:
        benchmark = run_synthetic_benchmark(
            null_world(n=spec.n_per_world, seed=seed),
            source_code_sha=spec.source_code_sha,
        )
        calibration_brier, calibration_log, calibration_promoted = _material_promotion(
            benchmark,
            candidate="calibration",
            brier_gain=spec.brier_material_gain,
            log_loss_gain=spec.log_loss_material_gain,
        )
        interaction_brier, interaction_log, interaction_promoted = _material_promotion(
            benchmark,
            candidate="interaction",
            brier_gain=spec.brier_material_gain,
            log_loss_gain=spec.log_loss_material_gain,
        )
        results.append(
            NullSeedResult(
                seed=seed,
                calibration_brier_gain=calibration_brier,
                calibration_log_loss_gain=calibration_log,
                interaction_brier_gain=interaction_brier,
                interaction_log_loss_gain=interaction_log,
                calibration_false_promotion=calibration_promoted,
                interaction_false_promotion=interaction_promoted,
                any_false_promotion=calibration_promoted or interaction_promoted,
            )
        )

    n_false = sum(result.any_false_promotion for result in results)
    rate = n_false / len(results)
    upper = _wilson_upper_bound(
        successes=n_false,
        trials=len(results),
        confidence_level=spec.confidence_level,
    )
    status: Literal["HEALTHY", "FAILED"] = (
        "HEALTHY" if upper <= spec.max_false_promotion_rate else "FAILED"
    )
    return NullCalibrationReport(
        campaign_spec_sha256=spec.semantic_sha256,
        campaign_id=spec.campaign_id,
        n_worlds=len(results),
        n_false_promotions=n_false,
        false_promotion_rate=rate,
        upper_confidence_bound=upper,
        max_allowed_false_promotion_rate=spec.max_false_promotion_rate,
        status=status,
        results=tuple(results),
    )
