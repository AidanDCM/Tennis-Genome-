from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

from tennis_genome.evaluation.metrics import (
    accuracy,
    binary_log_loss,
    brier_score,
    expected_calibration_error,
)
from tennis_genome.evaluation.paired_inference import (
    McNemarResult,
    PairedBootstrapResult,
    PairedPermutationResult,
    mcnemar_exact,
    paired_bootstrap_improvement,
    paired_sign_flip_test,
    per_match_brier_losses,
    per_match_log_losses,
)

SignalName = Literal["profile_gap", "genome"]
Tour = Literal["ATP", "WTA"]
_EXPERIMENT_ID = "MARKET-EDGE-001"
_DEVELOPMENT_END_YEAR = 2025
_MIN_PRIOR_ROWS = 1000
_RECENT_START_YEAR = 2021
_RECENT_END_YEAR = 2025
_LOGIT_CLIP = 1e-6
_BOOTSTRAP_RESAMPLES = 10_000
_PERMUTATION_RESAMPLES = 20_000


@dataclass(frozen=True)
class MarketSignalRow:
    match_id: str
    tour: Tour
    year: int
    outcome_a: bool
    market_probability_a: float
    signal: float

    def __post_init__(self) -> None:
        if not self.match_id:
            raise ValueError("match_id must be non-empty")
        if self.tour not in {"ATP", "WTA"}:
            raise ValueError("tour must be ATP or WTA")
        if self.year < 1900 or self.year > _DEVELOPMENT_END_YEAR:
            raise ValueError("MARKET-EDGE-001 is frozen through 2025")
        if not math.isfinite(self.market_probability_a):
            raise ValueError("market_probability_a must be finite")
        if not 0.0 < self.market_probability_a < 1.0:
            raise ValueError("market_probability_a must be in (0, 1)")
        if not math.isfinite(self.signal):
            raise ValueError("signal must be finite")


@dataclass(frozen=True)
class OffsetFit:
    intercept: float
    market_logit_slope: float
    beta: float | None
    signal_mean: float | None
    signal_sd: float | None
    train_n: int


@dataclass(frozen=True)
class MarketEdgePrediction:
    match_id: str
    tour: Tour
    signal_name: SignalName
    year: int
    outcome_a: bool
    market_probability_a: float
    control_probability_a: float
    challenger_probability_a: float
    signal: float
    fit_intercept_control: float
    fit_market_slope_control: float
    fit_intercept_challenger: float
    fit_market_slope_challenger: float
    fit_beta: float
    fit_signal_mean: float
    fit_signal_sd: float
    train_n: int


@dataclass(frozen=True)
class Score:
    n: int
    brier: float
    log_loss: float
    accuracy: float
    ece_10: float


@dataclass(frozen=True)
class PairedMetricInference:
    bootstrap: PairedBootstrapResult
    sign_flip: PairedPermutationResult


@dataclass(frozen=True)
class Comparison:
    market: Score
    recalibration_control: Score
    signal_challenger: Score
    brier_improvement_vs_control: float
    log_loss_improvement_vs_control: float
    accuracy_change_vs_control: float


@dataclass(frozen=True)
class YearResult:
    year: int
    n: int
    comparison: Comparison
    joint_proper_score_win: bool


@dataclass(frozen=True)
class PromotionDiagnostics:
    aggregate_brier_positive: bool
    aggregate_log_loss_positive: bool
    brier_bootstrap_lower_positive: bool
    log_loss_bootstrap_lower_positive: bool
    brier_sign_flip_p: float
    log_loss_sign_flip_p: float
    yearly_joint_win_count: int
    yearly_count: int
    yearly_joint_win_fraction: float
    yearly_stability_pass: bool
    recent_joint_proper_score_win: bool
    brier_single_year_concentration: float
    log_loss_single_year_concentration: float
    concentration_pass: bool
    pre_holm_candidate_pass: bool


@dataclass(frozen=True)
class MarketEdgeClaimReport:
    experiment_id: str
    tour: Tour
    signal_name: SignalName
    min_prior_rows: int
    prediction_n: int
    first_evaluation_year: int
    last_evaluation_year: int
    comparison: Comparison
    recent_comparison: Comparison | None
    brier_inference: PairedMetricInference
    log_loss_inference: PairedMetricInference
    mcnemar: McNemarResult
    yearly: tuple[YearResult, ...]
    promotion_diagnostics: PromotionDiagnostics
    predictions: tuple[MarketEdgePrediction, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _logit(probability: float) -> float:
    clipped = min(max(float(probability), _LOGIT_CLIP), 1.0 - _LOGIT_CLIP)
    return math.log(clipped / (1.0 - clipped))


def _sigmoid(value: float) -> float:
    return float(expit(value))


def _fit_offset_model(
    rows: list[MarketSignalRow],
    *,
    include_signal: bool,
) -> OffsetFit:
    """Fit chronological Platt-style market recalibration with optional signal.

    The primary control is alpha + gamma * logit(p_market). The challenger adds
    beta * z(signal), where signal scaling is fit on these training rows only.
    """

    if not rows:
        raise ValueError("market recalibration requires non-empty training rows")
    market_logits = np.asarray(
        [_logit(row.market_probability_a) for row in rows],
        dtype=float,
    )
    outcomes = np.asarray(
        [1.0 if row.outcome_a else 0.0 for row in rows],
        dtype=float,
    )

    signal_mean: float | None = None
    signal_sd: float | None = None
    z_signal: np.ndarray | None = None
    if include_signal:
        signal = np.asarray([row.signal for row in rows], dtype=float)
        signal_mean = float(np.mean(signal))
        signal_sd = float(np.std(signal, ddof=0))
        if not math.isfinite(signal_sd) or signal_sd <= 0.0:
            raise ValueError("training signal has zero or non-finite standard deviation")
        z_signal = (signal - signal_mean) / signal_sd

    def objective(parameters: np.ndarray) -> tuple[float, np.ndarray]:
        intercept = parameters[0]
        market_slope = parameters[1]
        linear = intercept + market_slope * market_logits
        if include_signal:
            assert z_signal is not None
            linear = linear + parameters[2] * z_signal
        loss = float(np.mean(np.logaddexp(0.0, linear) - outcomes * linear))
        probabilities = expit(linear)
        residual = probabilities - outcomes
        gradient_values = [
            float(np.mean(residual)),
            float(np.mean(residual * market_logits)),
        ]
        if include_signal:
            assert z_signal is not None
            gradient_values.append(float(np.mean(residual * z_signal)))
        return loss, np.asarray(gradient_values, dtype=float)

    initial = np.asarray(
        [0.0, 1.0, 0.0] if include_signal else [0.0, 1.0],
        dtype=float,
    )
    result = minimize(
        lambda parameters: objective(parameters)[0],
        initial,
        jac=lambda parameters: objective(parameters)[1],
        method="BFGS",
        options={"maxiter": 1000, "gtol": 1e-8},
    )
    if (
        not result.success
        or not np.all(np.isfinite(result.x))
        or not math.isfinite(float(result.fun))
        or not np.all(np.isfinite(result.jac))
    ):
        raise RuntimeError(f"market recalibration optimization failed: {result.message}")
    return OffsetFit(
        intercept=float(result.x[0]),
        market_logit_slope=float(result.x[1]),
        beta=float(result.x[2]) if include_signal else None,
        signal_mean=signal_mean,
        signal_sd=signal_sd,
        train_n=len(rows),
    )


def _predict_control(row: MarketSignalRow, fit: OffsetFit) -> float:
    return _sigmoid(fit.intercept + fit.market_logit_slope * _logit(row.market_probability_a))


def _predict_challenger(row: MarketSignalRow, fit: OffsetFit) -> float:
    if fit.beta is None or fit.signal_mean is None or fit.signal_sd is None:
        raise ValueError("challenger prediction requires signal fit")
    z_signal = (row.signal - fit.signal_mean) / fit.signal_sd
    return _sigmoid(
        fit.intercept
        + fit.market_logit_slope * _logit(row.market_probability_a)
        + fit.beta * z_signal
    )


def generate_market_edge_predictions(
    rows: list[MarketSignalRow],
    *,
    signal_name: SignalName,
    min_prior_rows: int = _MIN_PRIOR_ROWS,
) -> list[MarketEdgePrediction]:
    if signal_name not in {"profile_gap", "genome"}:
        raise ValueError("unsupported signal_name")
    if min_prior_rows <= 0:
        raise ValueError("min_prior_rows must be positive")
    if not rows:
        raise ValueError("rows must be non-empty")
    if any(row.year > _DEVELOPMENT_END_YEAR for row in rows):
        raise ValueError("MARKET-EDGE-001 is frozen through 2025")
    tours = {row.tour for row in rows}
    if len(tours) != 1:
        raise ValueError("one market-edge claim must contain exactly one tour")
    match_ids = [row.match_id for row in rows]
    if len(match_ids) != len(set(match_ids)):
        raise ValueError("market-edge rows contain duplicate match_id values")

    ordered = sorted(rows, key=lambda row: (row.year, row.match_id))
    predictions: list[MarketEdgePrediction] = []
    for test_year in sorted({row.year for row in ordered}):
        train = [row for row in ordered if row.year < test_year]
        test = [row for row in ordered if row.year == test_year]
        if len(train) < min_prior_rows or not test:
            continue
        control_fit = _fit_offset_model(train, include_signal=False)
        challenger_fit = _fit_offset_model(train, include_signal=True)
        assert challenger_fit.beta is not None
        assert challenger_fit.signal_mean is not None
        assert challenger_fit.signal_sd is not None
        for row in test:
            predictions.append(
                MarketEdgePrediction(
                    match_id=row.match_id,
                    tour=row.tour,
                    signal_name=signal_name,
                    year=row.year,
                    outcome_a=row.outcome_a,
                    market_probability_a=row.market_probability_a,
                    control_probability_a=_predict_control(row, control_fit),
                    challenger_probability_a=_predict_challenger(row, challenger_fit),
                    signal=row.signal,
                    fit_intercept_control=control_fit.intercept,
                    fit_market_slope_control=control_fit.market_logit_slope,
                    fit_intercept_challenger=challenger_fit.intercept,
                    fit_market_slope_challenger=challenger_fit.market_logit_slope,
                    fit_beta=challenger_fit.beta,
                    fit_signal_mean=challenger_fit.signal_mean,
                    fit_signal_sd=challenger_fit.signal_sd,
                    train_n=len(train),
                )
            )
    if not predictions:
        raise ValueError("no eligible chronological evaluation years")
    return predictions


def _score(
    predictions: list[MarketEdgePrediction],
    *,
    probability_field: str,
) -> Score:
    outcomes = [row.outcome_a for row in predictions]
    probabilities = [float(getattr(row, probability_field)) for row in predictions]
    return Score(
        n=len(predictions),
        brier=brier_score(outcomes, probabilities),
        log_loss=binary_log_loss(outcomes, probabilities),
        accuracy=accuracy(outcomes, probabilities),
        ece_10=expected_calibration_error(outcomes, probabilities, n_bins=10),
    )


def _comparison(predictions: list[MarketEdgePrediction]) -> Comparison:
    market = _score(predictions, probability_field="market_probability_a")
    control = _score(predictions, probability_field="control_probability_a")
    challenger = _score(predictions, probability_field="challenger_probability_a")
    return Comparison(
        market=market,
        recalibration_control=control,
        signal_challenger=challenger,
        brier_improvement_vs_control=control.brier - challenger.brier,
        log_loss_improvement_vs_control=control.log_loss - challenger.log_loss,
        accuracy_change_vs_control=challenger.accuracy - control.accuracy,
    )


def _seed(*parts: object) -> int:
    key = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _metric_inference(
    predictions: list[MarketEdgePrediction],
    *,
    metric: Literal["brier", "log_loss"],
    tour: Tour,
    signal_name: SignalName,
) -> PairedMetricInference:
    outcomes = [row.outcome_a for row in predictions]
    control = [row.control_probability_a for row in predictions]
    challenger = [row.challenger_probability_a for row in predictions]
    if metric == "brier":
        control_losses = per_match_brier_losses(outcomes, control)
        challenger_losses = per_match_brier_losses(outcomes, challenger)
    else:
        control_losses = per_match_log_losses(outcomes, control)
        challenger_losses = per_match_log_losses(outcomes, challenger)
    return PairedMetricInference(
        bootstrap=paired_bootstrap_improvement(
            control_losses,
            challenger_losses,
            confidence_level=0.95,
            n_resamples=_BOOTSTRAP_RESAMPLES,
            seed=_seed(_EXPERIMENT_ID, tour, signal_name, metric, "bootstrap"),
        ),
        sign_flip=paired_sign_flip_test(
            control_losses,
            challenger_losses,
            n_resamples=_PERMUTATION_RESAMPLES,
            seed=_seed(_EXPERIMENT_ID, tour, signal_name, metric, "sign-flip"),
        ),
    )


def _year_concentration(
    predictions: list[MarketEdgePrediction],
    *,
    metric: Literal["brier", "log_loss"],
) -> float:
    contributions: list[float] = []
    for year in sorted({row.year for row in predictions}):
        subset = [row for row in predictions if row.year == year]
        outcomes = [row.outcome_a for row in subset]
        control = [row.control_probability_a for row in subset]
        challenger = [row.challenger_probability_a for row in subset]
        if metric == "brier":
            base_losses = per_match_brier_losses(outcomes, control)
            candidate_losses = per_match_brier_losses(outcomes, challenger)
        else:
            base_losses = per_match_log_losses(outcomes, control)
            candidate_losses = per_match_log_losses(outcomes, challenger)
        contributions.append(
            sum(
                base - candidate
                for base, candidate in zip(base_losses, candidate_losses, strict=True)
            )
        )
    magnitudes = [abs(value) for value in contributions]
    total = sum(magnitudes)
    if total <= 0.0:
        return 1.0
    return max(magnitudes) / total


def run_market_edge_claim(
    rows: list[MarketSignalRow],
    *,
    signal_name: SignalName,
    min_prior_rows: int = _MIN_PRIOR_ROWS,
) -> MarketEdgeClaimReport:
    predictions = generate_market_edge_predictions(
        rows,
        signal_name=signal_name,
        min_prior_rows=min_prior_rows,
    )
    tour = predictions[0].tour
    comparison = _comparison(predictions)
    brier_inference = _metric_inference(
        predictions,
        metric="brier",
        tour=tour,
        signal_name=signal_name,
    )
    log_loss_inference = _metric_inference(
        predictions,
        metric="log_loss",
        tour=tour,
        signal_name=signal_name,
    )
    yearly_results: list[YearResult] = []
    for year in sorted({row.year for row in predictions}):
        subset = [row for row in predictions if row.year == year]
        year_comparison = _comparison(subset)
        yearly_results.append(
            YearResult(
                year=year,
                n=len(subset),
                comparison=year_comparison,
                joint_proper_score_win=(
                    year_comparison.brier_improvement_vs_control > 0.0
                    and year_comparison.log_loss_improvement_vs_control > 0.0
                ),
            )
        )
    yearly = tuple(yearly_results)
    recent_rows = [row for row in predictions if _RECENT_START_YEAR <= row.year <= _RECENT_END_YEAR]
    recent = _comparison(recent_rows) if recent_rows else None
    year_wins = sum(item.joint_proper_score_win for item in yearly)
    year_fraction = year_wins / len(yearly)
    brier_concentration = _year_concentration(predictions, metric="brier")
    log_concentration = _year_concentration(predictions, metric="log_loss")
    recent_joint = bool(
        recent is not None
        and recent.brier_improvement_vs_control > 0.0
        and recent.log_loss_improvement_vs_control > 0.0
    )
    concentration_pass = brier_concentration <= 0.5 and log_concentration <= 0.5
    diagnostics = PromotionDiagnostics(
        aggregate_brier_positive=comparison.brier_improvement_vs_control > 0.0,
        aggregate_log_loss_positive=comparison.log_loss_improvement_vs_control > 0.0,
        brier_bootstrap_lower_positive=brier_inference.bootstrap.lower > 0.0,
        log_loss_bootstrap_lower_positive=log_loss_inference.bootstrap.lower > 0.0,
        brier_sign_flip_p=brier_inference.sign_flip.p_value,
        log_loss_sign_flip_p=log_loss_inference.sign_flip.p_value,
        yearly_joint_win_count=year_wins,
        yearly_count=len(yearly),
        yearly_joint_win_fraction=year_fraction,
        yearly_stability_pass=year_fraction >= 0.60,
        recent_joint_proper_score_win=recent_joint,
        brier_single_year_concentration=brier_concentration,
        log_loss_single_year_concentration=log_concentration,
        concentration_pass=concentration_pass,
        pre_holm_candidate_pass=bool(
            comparison.brier_improvement_vs_control > 0.0
            and comparison.log_loss_improvement_vs_control > 0.0
            and brier_inference.bootstrap.lower > 0.0
            and log_loss_inference.bootstrap.lower > 0.0
            and year_fraction >= 0.60
            and recent_joint
            and concentration_pass
        ),
    )
    return MarketEdgeClaimReport(
        experiment_id=_EXPERIMENT_ID,
        tour=tour,
        signal_name=signal_name,
        min_prior_rows=min_prior_rows,
        prediction_n=len(predictions),
        first_evaluation_year=min(row.year for row in predictions),
        last_evaluation_year=max(row.year for row in predictions),
        comparison=comparison,
        recent_comparison=recent,
        brier_inference=brier_inference,
        log_loss_inference=log_loss_inference,
        mcnemar=mcnemar_exact(
            [row.outcome_a for row in predictions],
            [row.control_probability_a for row in predictions],
            [row.challenger_probability_a for row in predictions],
        ),
        yearly=yearly,
        promotion_diagnostics=diagnostics,
        predictions=tuple(predictions),
    )
