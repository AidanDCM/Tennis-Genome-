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
TrainingWindow = Literal["expanding", "trailing_3y"]
_EXPERIMENT_ID = "MARKET-EDGE-ADV-001"
_DEVELOPMENT_END_YEAR = 2025
_MIN_PRIOR_ROWS = 1000
_RECENT_START_YEAR = 2021
_RECENT_END_YEAR = 2025
_LOGIT_CLIP = 1e-6
_BOOTSTRAP_RESAMPLES = 10_000
_PERMUTATION_RESAMPLES = 20_000
_TRAILING_YEARS = 3


@dataclass(frozen=True)
class MarketCoreSignalRow:
    match_id: str
    tour: Tour
    year: int
    outcome_a: bool
    market_probability_a: float
    core_probability_a: float
    signal: float

    def __post_init__(self) -> None:
        if not self.match_id:
            raise ValueError("match_id must be non-empty")
        if self.tour not in {"ATP", "WTA"}:
            raise ValueError("tour must be ATP or WTA")
        if self.year < 1900 or self.year > _DEVELOPMENT_END_YEAR:
            raise ValueError("MARKET-EDGE-ADV-001 is frozen through 2025")
        for name, value in (
            ("market_probability_a", self.market_probability_a),
            ("core_probability_a", self.core_probability_a),
        ):
            if not math.isfinite(value) or not 0.0 < value < 1.0:
                raise ValueError(f"{name} must be finite and in (0, 1)")
        if not math.isfinite(self.signal):
            raise ValueError("signal must be finite")


@dataclass(frozen=True)
class AdversarialFit:
    intercept: float
    market_logit_slope: float
    core_logit_slope: float | None
    beta: float | None
    signal_mean: float | None
    signal_sd: float | None
    train_n: int
    train_start_year: int
    train_end_year: int
    market_core_correlation: float | None
    market_signal_correlation: float | None
    core_signal_correlation: float | None


@dataclass(frozen=True)
class AdversarialPrediction:
    match_id: str
    tour: Tour
    signal_name: SignalName
    training_window: TrainingWindow
    year: int
    outcome_a: bool
    market_probability_a: float
    core_probability_a: float
    signal: float
    market_only_probability_a: float
    market_core_probability_a: float
    challenger_probability_a: float
    market_only_fit: AdversarialFit
    market_core_fit: AdversarialFit
    challenger_fit: AdversarialFit


@dataclass(frozen=True)
class Score:
    n: int
    brier: float
    log_loss: float
    accuracy: float
    ece_10: float


@dataclass(frozen=True)
class Comparison:
    market: Score
    core: Score
    market_only_recalibration: Score
    market_core_control: Score
    signal_challenger: Score
    brier_improvement_vs_market_core: float
    log_loss_improvement_vs_market_core: float
    accuracy_change_vs_market_core: float
    brier_improvement_market_core_vs_market_only: float
    log_loss_improvement_market_core_vs_market_only: float


@dataclass(frozen=True)
class PairedMetricInference:
    bootstrap: PairedBootstrapResult
    sign_flip: PairedPermutationResult


@dataclass(frozen=True)
class YearResult:
    year: int
    n: int
    comparison: Comparison
    joint_proper_score_win: bool
    market_only_fit: AdversarialFit
    market_core_fit: AdversarialFit
    challenger_fit: AdversarialFit


@dataclass(frozen=True)
class WindowSummary:
    training_window: TrainingWindow
    prediction_n: int
    first_evaluation_year: int
    last_evaluation_year: int
    comparison: Comparison
    recent_comparison: Comparison | None
    yearly: tuple[YearResult, ...]
    predictions: tuple[AdversarialPrediction, ...]


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
    robustness_direction_conflict: bool | None
    pre_holm_candidate_pass: bool


@dataclass(frozen=True)
class MarketEdgeAdversarialClaimReport:
    experiment_id: str
    tour: Tour
    signal_name: SignalName
    min_prior_rows: int
    primary: WindowSummary
    trailing_3y_robustness: WindowSummary | None
    brier_inference: PairedMetricInference
    log_loss_inference: PairedMetricInference
    mcnemar: McNemarResult
    promotion_diagnostics: PromotionDiagnostics

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _logit(probability: float) -> float:
    clipped = min(max(float(probability), _LOGIT_CLIP), 1.0 - _LOGIT_CLIP)
    return math.log(clipped / (1.0 - clipped))


def _sigmoid(value: float) -> float:
    return float(expit(value))


def _correlation(left: np.ndarray, right: np.ndarray) -> float | None:
    if left.size < 2 or right.size < 2:
        return None
    left_sd = float(np.std(left, ddof=0))
    right_sd = float(np.std(right, ddof=0))
    if left_sd <= 0.0 or right_sd <= 0.0:
        return None
    value = float(np.corrcoef(left, right)[0, 1])
    return value if math.isfinite(value) else None


def _fit_model(
    rows: list[MarketCoreSignalRow],
    *,
    include_core: bool,
    include_signal: bool,
) -> AdversarialFit:
    if not rows:
        raise ValueError("adversarial fit requires non-empty training rows")
    if include_signal and not include_core:
        raise ValueError("signal challenger requires the Market + Core control")

    market_logits = np.asarray(
        [_logit(row.market_probability_a) for row in rows],
        dtype=float,
    )
    core_logits = np.asarray(
        [_logit(row.core_probability_a) for row in rows],
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

    columns = [np.ones(len(rows), dtype=float), market_logits]
    if include_core:
        columns.append(core_logits)
    if include_signal:
        assert z_signal is not None
        columns.append(z_signal)
    design = np.column_stack(columns)
    if int(np.linalg.matrix_rank(design)) < design.shape[1]:
        raise ValueError("adversarial logistic design is rank deficient")

    def objective(parameters: np.ndarray) -> tuple[float, np.ndarray]:
        linear = design @ parameters
        loss = float(np.mean(np.logaddexp(0.0, linear) - outcomes * linear))
        residual = expit(linear) - outcomes
        gradient = np.mean(design * residual[:, None], axis=0)
        return loss, np.asarray(gradient, dtype=float)

    if include_signal:
        initial = np.asarray([0.0, 1.0, 0.0, 0.0], dtype=float)
    elif include_core:
        initial = np.asarray([0.0, 1.0, 0.0], dtype=float)
    else:
        initial = np.asarray([0.0, 1.0], dtype=float)

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
        raise RuntimeError(f"adversarial logistic optimization failed: {result.message}")

    market_core_corr = _correlation(market_logits, core_logits) if include_core else None
    market_signal_corr = (
        _correlation(market_logits, z_signal) if include_signal and z_signal is not None else None
    )
    core_signal_corr = (
        _correlation(core_logits, z_signal) if include_signal and z_signal is not None else None
    )
    years = [row.year for row in rows]
    core_index = 2 if include_core else None
    beta_index = 3 if include_signal else None
    return AdversarialFit(
        intercept=float(result.x[0]),
        market_logit_slope=float(result.x[1]),
        core_logit_slope=(None if core_index is None else float(result.x[core_index])),
        beta=None if beta_index is None else float(result.x[beta_index]),
        signal_mean=signal_mean,
        signal_sd=signal_sd,
        train_n=len(rows),
        train_start_year=min(years),
        train_end_year=max(years),
        market_core_correlation=market_core_corr,
        market_signal_correlation=market_signal_corr,
        core_signal_correlation=core_signal_corr,
    )


def _predict(row: MarketCoreSignalRow, fit: AdversarialFit) -> float:
    linear = fit.intercept + fit.market_logit_slope * _logit(row.market_probability_a)
    if fit.core_logit_slope is not None:
        linear += fit.core_logit_slope * _logit(row.core_probability_a)
    if fit.beta is not None:
        if fit.signal_mean is None or fit.signal_sd is None:
            raise ValueError("signal fit is missing training standardization")
        linear += fit.beta * ((row.signal - fit.signal_mean) / fit.signal_sd)
    return _sigmoid(linear)


def _training_rows(
    ordered: list[MarketCoreSignalRow],
    *,
    test_year: int,
    training_window: TrainingWindow,
) -> list[MarketCoreSignalRow]:
    if training_window == "expanding":
        return [row for row in ordered if row.year < test_year]
    if training_window == "trailing_3y":
        lower = test_year - _TRAILING_YEARS
        return [row for row in ordered if lower <= row.year < test_year]
    raise ValueError("unsupported training_window")


def generate_adversarial_predictions(
    rows: list[MarketCoreSignalRow],
    *,
    signal_name: SignalName,
    training_window: TrainingWindow = "expanding",
    min_prior_rows: int = _MIN_PRIOR_ROWS,
) -> list[AdversarialPrediction]:
    if signal_name not in {"profile_gap", "genome"}:
        raise ValueError("unsupported signal_name")
    if training_window not in {"expanding", "trailing_3y"}:
        raise ValueError("unsupported training_window")
    if min_prior_rows <= 0:
        raise ValueError("min_prior_rows must be positive")
    if not rows:
        raise ValueError("rows must be non-empty")
    if any(row.year > _DEVELOPMENT_END_YEAR for row in rows):
        raise ValueError("MARKET-EDGE-ADV-001 is frozen through 2025")
    tours = {row.tour for row in rows}
    if len(tours) != 1:
        raise ValueError("one adversarial claim must contain exactly one tour")
    match_ids = [row.match_id for row in rows]
    if len(match_ids) != len(set(match_ids)):
        raise ValueError("adversarial rows contain duplicate match_id values")

    ordered = sorted(rows, key=lambda row: (row.year, row.match_id))
    predictions: list[AdversarialPrediction] = []
    for test_year in sorted({row.year for row in ordered}):
        train = _training_rows(
            ordered,
            test_year=test_year,
            training_window=training_window,
        )
        test = [row for row in ordered if row.year == test_year]
        if len(train) < min_prior_rows or not test:
            continue
        market_only_fit = _fit_model(train, include_core=False, include_signal=False)
        market_core_fit = _fit_model(train, include_core=True, include_signal=False)
        challenger_fit = _fit_model(train, include_core=True, include_signal=True)
        for row in test:
            predictions.append(
                AdversarialPrediction(
                    match_id=row.match_id,
                    tour=row.tour,
                    signal_name=signal_name,
                    training_window=training_window,
                    year=row.year,
                    outcome_a=row.outcome_a,
                    market_probability_a=row.market_probability_a,
                    core_probability_a=row.core_probability_a,
                    signal=row.signal,
                    market_only_probability_a=_predict(row, market_only_fit),
                    market_core_probability_a=_predict(row, market_core_fit),
                    challenger_probability_a=_predict(row, challenger_fit),
                    market_only_fit=market_only_fit,
                    market_core_fit=market_core_fit,
                    challenger_fit=challenger_fit,
                )
            )
    return predictions


def _score(
    predictions: list[AdversarialPrediction],
    *,
    probability_field: str,
) -> Score:
    if not predictions:
        raise ValueError("cannot score an empty adversarial prediction set")
    outcomes = [row.outcome_a for row in predictions]
    probabilities = [float(getattr(row, probability_field)) for row in predictions]
    return Score(
        n=len(predictions),
        brier=brier_score(outcomes, probabilities),
        log_loss=binary_log_loss(outcomes, probabilities),
        accuracy=accuracy(outcomes, probabilities),
        ece_10=expected_calibration_error(outcomes, probabilities, n_bins=10),
    )


def _comparison(predictions: list[AdversarialPrediction]) -> Comparison:
    market = _score(predictions, probability_field="market_probability_a")
    core = _score(predictions, probability_field="core_probability_a")
    market_only = _score(predictions, probability_field="market_only_probability_a")
    market_core = _score(predictions, probability_field="market_core_probability_a")
    challenger = _score(predictions, probability_field="challenger_probability_a")
    return Comparison(
        market=market,
        core=core,
        market_only_recalibration=market_only,
        market_core_control=market_core,
        signal_challenger=challenger,
        brier_improvement_vs_market_core=market_core.brier - challenger.brier,
        log_loss_improvement_vs_market_core=market_core.log_loss - challenger.log_loss,
        accuracy_change_vs_market_core=challenger.accuracy - market_core.accuracy,
        brier_improvement_market_core_vs_market_only=market_only.brier - market_core.brier,
        log_loss_improvement_market_core_vs_market_only=(
            market_only.log_loss - market_core.log_loss
        ),
    )


def _window_summary(
    predictions: list[AdversarialPrediction],
    *,
    training_window: TrainingWindow,
) -> WindowSummary:
    if not predictions:
        raise ValueError("cannot summarize an empty adversarial window")
    yearly_results: list[YearResult] = []
    for year in sorted({row.year for row in predictions}):
        subset = [row for row in predictions if row.year == year]
        comparison = _comparison(subset)
        first = subset[0]
        yearly_results.append(
            YearResult(
                year=year,
                n=len(subset),
                comparison=comparison,
                joint_proper_score_win=bool(
                    comparison.brier_improvement_vs_market_core > 0.0
                    and comparison.log_loss_improvement_vs_market_core > 0.0
                ),
                market_only_fit=first.market_only_fit,
                market_core_fit=first.market_core_fit,
                challenger_fit=first.challenger_fit,
            )
        )
    recent_rows = [row for row in predictions if _RECENT_START_YEAR <= row.year <= _RECENT_END_YEAR]
    return WindowSummary(
        training_window=training_window,
        prediction_n=len(predictions),
        first_evaluation_year=min(row.year for row in predictions),
        last_evaluation_year=max(row.year for row in predictions),
        comparison=_comparison(predictions),
        recent_comparison=_comparison(recent_rows) if recent_rows else None,
        yearly=tuple(yearly_results),
        predictions=tuple(predictions),
    )


def _seed(*parts: object) -> int:
    key = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _metric_inference(
    predictions: list[AdversarialPrediction],
    *,
    metric: Literal["brier", "log_loss"],
    tour: Tour,
    signal_name: SignalName,
) -> PairedMetricInference:
    outcomes = [row.outcome_a for row in predictions]
    control = [row.market_core_probability_a for row in predictions]
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
    predictions: list[AdversarialPrediction],
    *,
    metric: Literal["brier", "log_loss"],
) -> float:
    contributions: list[float] = []
    for year in sorted({row.year for row in predictions}):
        subset = [row for row in predictions if row.year == year]
        outcomes = [row.outcome_a for row in subset]
        control = [row.market_core_probability_a for row in subset]
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


def run_market_edge_adversarial_claim(
    rows: list[MarketCoreSignalRow],
    *,
    signal_name: SignalName,
    min_prior_rows: int = _MIN_PRIOR_ROWS,
) -> MarketEdgeAdversarialClaimReport:
    primary_predictions = generate_adversarial_predictions(
        rows,
        signal_name=signal_name,
        training_window="expanding",
        min_prior_rows=min_prior_rows,
    )
    if not primary_predictions:
        raise ValueError("no eligible chronological evaluation years for primary adversary")
    primary = _window_summary(primary_predictions, training_window="expanding")
    tour = primary_predictions[0].tour

    robustness_predictions = generate_adversarial_predictions(
        rows,
        signal_name=signal_name,
        training_window="trailing_3y",
        min_prior_rows=min_prior_rows,
    )
    robustness = (
        _window_summary(robustness_predictions, training_window="trailing_3y")
        if robustness_predictions
        else None
    )

    brier_inference = _metric_inference(
        primary_predictions,
        metric="brier",
        tour=tour,
        signal_name=signal_name,
    )
    log_loss_inference = _metric_inference(
        primary_predictions,
        metric="log_loss",
        tour=tour,
        signal_name=signal_name,
    )
    year_wins = sum(item.joint_proper_score_win for item in primary.yearly)
    year_fraction = year_wins / len(primary.yearly)
    recent = primary.recent_comparison
    recent_joint = bool(
        recent is not None
        and recent.brier_improvement_vs_market_core > 0.0
        and recent.log_loss_improvement_vs_market_core > 0.0
    )
    brier_concentration = _year_concentration(primary_predictions, metric="brier")
    log_concentration = _year_concentration(primary_predictions, metric="log_loss")
    concentration_pass = brier_concentration <= 0.5 and log_concentration <= 0.5

    robustness_conflict: bool | None = None
    if robustness is not None:
        primary_direction = bool(
            primary.comparison.brier_improvement_vs_market_core > 0.0
            and primary.comparison.log_loss_improvement_vs_market_core > 0.0
        )
        robustness_direction = bool(
            robustness.comparison.brier_improvement_vs_market_core > 0.0
            and robustness.comparison.log_loss_improvement_vs_market_core > 0.0
        )
        robustness_conflict = primary_direction != robustness_direction

    pre_holm = bool(
        primary.comparison.brier_improvement_vs_market_core > 0.0
        and primary.comparison.log_loss_improvement_vs_market_core > 0.0
        and brier_inference.bootstrap.lower > 0.0
        and log_loss_inference.bootstrap.lower > 0.0
        and year_fraction >= 0.60
        and recent_joint
        and concentration_pass
    )
    diagnostics = PromotionDiagnostics(
        aggregate_brier_positive=(primary.comparison.brier_improvement_vs_market_core > 0.0),
        aggregate_log_loss_positive=(primary.comparison.log_loss_improvement_vs_market_core > 0.0),
        brier_bootstrap_lower_positive=brier_inference.bootstrap.lower > 0.0,
        log_loss_bootstrap_lower_positive=log_loss_inference.bootstrap.lower > 0.0,
        brier_sign_flip_p=brier_inference.sign_flip.p_value,
        log_loss_sign_flip_p=log_loss_inference.sign_flip.p_value,
        yearly_joint_win_count=year_wins,
        yearly_count=len(primary.yearly),
        yearly_joint_win_fraction=year_fraction,
        yearly_stability_pass=year_fraction >= 0.60,
        recent_joint_proper_score_win=recent_joint,
        brier_single_year_concentration=brier_concentration,
        log_loss_single_year_concentration=log_concentration,
        concentration_pass=concentration_pass,
        robustness_direction_conflict=robustness_conflict,
        pre_holm_candidate_pass=pre_holm,
    )
    return MarketEdgeAdversarialClaimReport(
        experiment_id=_EXPERIMENT_ID,
        tour=tour,
        signal_name=signal_name,
        min_prior_rows=min_prior_rows,
        primary=primary,
        trailing_3y_robustness=robustness,
        brier_inference=brier_inference,
        log_loss_inference=log_loss_inference,
        mcnemar=mcnemar_exact(
            [row.outcome_a for row in primary_predictions],
            [row.market_core_probability_a for row in primary_predictions],
            [row.challenger_probability_a for row in primary_predictions],
        ),
        promotion_diagnostics=diagnostics,
    )
