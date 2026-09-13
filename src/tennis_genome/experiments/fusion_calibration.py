from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from tennis_genome.calibration.probability import make_calibrator
from tennis_genome.data.canonical import HistoricalMatch, Tour
from tennis_genome.data.manifest import verify_canonical_manifest
from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.evaluation.metrics import (
    accuracy,
    binary_log_loss,
    brier_score,
    expected_calibration_error,
)
from tennis_genome.experiments.genome_adversarial_controls import (
    PredictionRow as AdversarialPredictionRow,
)
from tennis_genome.experiments.genome_adversarial_controls import (
    run_genome_adversarial_controls,
)

_DEVELOPMENT_END_YEAR = 2025
_RECENT_START_YEAR = 2021
_RECENT_END_YEAR = 2025
_CALIBRATORS = ("identity", "platt", "beta", "isotonic")
_NON_IDENTITY_TIE_ORDER = {"platt": 0, "beta": 1, "isotonic": 2}


@dataclass(frozen=True)
class Score:
    n: int
    brier: float
    log_loss: float
    accuracy: float
    ece_10: float


@dataclass(frozen=True)
class BaseProbabilityRow:
    match_id: str
    year: int
    outcome_a: bool
    core_control_probability_a: float
    alignment_probability_a: float


@dataclass(frozen=True)
class FusionPredictionRow:
    match_id: str
    year: int
    outcome_a: bool
    core_control_probability_a: float
    alignment_probability_a: float
    f0_alignment_identity: float
    f1_alignment_recalibration: float
    f2_equal_logit_blend: float
    f3_two_view_fusion: float


@dataclass(frozen=True)
class FusionYearResult:
    year: int
    n: int
    train_n: int
    f0: Score
    f1: Score
    f2: Score
    f3: Score
    f3_joint_win_vs_f1: bool
    f3_standardized_core_coefficient: float
    f3_standardized_alignment_coefficient: float
    f3_intercept: float


@dataclass(frozen=True)
class FusionComparison:
    n: int
    f0: Score
    f1: Score
    f2: Score
    f3: Score
    f3_vs_f1_brier_improvement: float
    f3_vs_f1_log_loss_improvement: float
    f3_vs_f0_brier_improvement: float
    f3_vs_f0_log_loss_improvement: float


@dataclass(frozen=True)
class FusionGate:
    aggregate_brier_better_than_recalibration_control: bool
    aggregate_log_loss_better_than_recalibration_control: bool
    joint_year_win_count: int
    evaluated_year_count: int
    joint_year_win_rate: float
    at_least_60_percent_joint_year_wins: bool
    recent_brier_not_worse: bool | None
    recent_log_loss_not_worse: bool | None
    passed: bool


@dataclass(frozen=True)
class DisagreementQuintile:
    quintile: int
    n: int
    mean_absolute_probability_disagreement: float
    core_control_brier: float
    alignment_brier: float
    fusion_brier: float


@dataclass(frozen=True)
class CalibrationYearResult:
    year: int
    n: int
    train_n: int
    score: Score
    joint_win_vs_identity: bool | None


@dataclass(frozen=True)
class CalibrationMethodResult:
    name: str
    score: Score
    recent_score: Score | None
    aggregate_brier_improvement_vs_identity: float
    aggregate_log_loss_improvement_vs_identity: float
    aggregate_ece_change_vs_identity: float
    joint_year_win_count: int
    evaluated_year_count: int
    joint_year_win_rate: float
    recent_brier_improvement_vs_identity: float | None
    recent_log_loss_improvement_vs_identity: float | None
    passed_promotion_gate: bool
    yearly: tuple[CalibrationYearResult, ...]


@dataclass(frozen=True)
class CandidateCalibrationResult:
    candidate: str
    population_n: int
    selected_calibrator: str
    methods: tuple[CalibrationMethodResult, ...]


@dataclass(frozen=True)
class ArchitectureDecision:
    fusion_promoted: bool
    selected_probability_candidate: str
    selected_calibrator: str
    note: str


@dataclass(frozen=True)
class FusionCalibrationReport:
    experiment_id: str
    tour: Tour
    development_end_year: int
    alignment_representation: str
    min_core_train_matches: int
    min_neighbor_pool: int
    min_meta_train_rows: int
    min_fusion_train_rows: int
    min_calibration_rows: int
    base_population_n: int
    fusion_population_n: int
    comparison: FusionComparison
    recent_comparison: FusionComparison | None
    yearly: tuple[FusionYearResult, ...]
    fusion_gate: FusionGate
    disagreement_quintiles: tuple[DisagreementQuintile, ...]
    calibration: tuple[CandidateCalibrationResult, ...]
    architecture_decision: ArchitectureDecision
    predictions: tuple[FusionPredictionRow, ...]


def _clip_probability(value: float) -> float:
    return min(max(float(value), 1e-6), 1.0 - 1e-6)


def _logit(value: float) -> float:
    p = _clip_probability(value)
    return math.log(p / (1.0 - p))


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _fixed_equal_logit_blend(core: float, alignment: float) -> float:
    return _sigmoid(0.5 * _logit(core) + 0.5 * _logit(alignment))


def _score_from_values(outcomes: list[bool], probabilities: list[float]) -> Score:
    if not outcomes or len(outcomes) != len(probabilities):
        raise ValueError("score inputs must have equal non-zero length")
    return Score(
        n=len(outcomes),
        brier=brier_score(outcomes, probabilities),
        log_loss=binary_log_loss(outcomes, probabilities),
        accuracy=accuracy(outcomes, probabilities),
        ece_10=expected_calibration_error(outcomes, probabilities, n_bins=10),
    )


def _score(rows: list[FusionPredictionRow], field: str) -> Score:
    return _score_from_values(
        [row.outcome_a for row in rows],
        [float(getattr(row, field)) for row in rows],
    )


def _comparison(rows: list[FusionPredictionRow]) -> FusionComparison:
    if not rows:
        raise ValueError("cannot compare an empty fusion population")
    f0 = _score(rows, "f0_alignment_identity")
    f1 = _score(rows, "f1_alignment_recalibration")
    f2 = _score(rows, "f2_equal_logit_blend")
    f3 = _score(rows, "f3_two_view_fusion")
    return FusionComparison(
        n=len(rows),
        f0=f0,
        f1=f1,
        f2=f2,
        f3=f3,
        f3_vs_f1_brier_improvement=f1.brier - f3.brier,
        f3_vs_f1_log_loss_improvement=f1.log_loss - f3.log_loss,
        f3_vs_f0_brier_improvement=f0.brier - f3.brier,
        f3_vs_f0_log_loss_improvement=f0.log_loss - f3.log_loss,
    )


def _alignment_probability(row: AdversarialPredictionRow, *, tour: Tour) -> float:
    if tour == "ATP":
        return row.full_genome_probability_a
    if tour == "WTA":
        return row.core_neighborhood_probability_a
    raise ValueError(f"unsupported tour: {tour!r}")


def _base_probability_rows(
    matches: list[HistoricalMatch],
    *,
    tour: Tour,
    min_core_train_matches: int,
    min_neighbor_pool: int,
    min_meta_train_rows: int,
    exclude_retirements: bool,
) -> list[BaseProbabilityRow]:
    selected = [match for match in matches if match.pre_match.tour == tour]
    if any(match.pre_match.event_date.year > _DEVELOPMENT_END_YEAR for match in selected):
        raise ValueError("post-2025 selected-tour data are forbidden in FUSION-CAL-001")

    report = run_genome_adversarial_controls(
        matches,
        tour=tour,
        min_core_train_matches=min_core_train_matches,
        min_neighbor_pool=min_neighbor_pool,
        min_meta_train_rows=min_meta_train_rows,
        exclude_retirements=exclude_retirements,
    )
    rows = [
        BaseProbabilityRow(
            match_id=row.match_id,
            year=row.year,
            outcome_a=row.outcome_a,
            core_control_probability_a=row.calibration_control_probability_a,
            alignment_probability_a=_alignment_probability(row, tour=tour),
        )
        for row in report.predictions
    ]
    if not rows:
        raise ValueError("GENOME-ADV-001 produced no base fusion rows")
    return sorted(rows, key=lambda row: (row.year, row.match_id))


def _fit_logistic(matrix: list[list[float]], outcomes: list[bool]) -> Pipeline:
    if not matrix or len(matrix) != len(outcomes):
        raise ValueError("fusion fit inputs must have equal non-zero length")
    if len(set(outcomes)) < 2:
        raise ValueError("fusion fit requires both outcome classes")
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000),
    )
    model.fit(matrix, [int(value) for value in outcomes])
    return model


def _f1_features(rows: list[BaseProbabilityRow]) -> list[list[float]]:
    return [[_logit(row.alignment_probability_a)] for row in rows]


def _f3_features(rows: list[BaseProbabilityRow]) -> list[list[float]]:
    return [
        [
            _logit(row.core_control_probability_a),
            _logit(row.alignment_probability_a),
        ]
        for row in rows
    ]


def _model_coefficients(model: Pipeline) -> tuple[list[float], float]:
    logistic = model[-1]
    return logistic.coef_[0].astype(float).tolist(), float(logistic.intercept_[0])


def _fusion_oof_from_base_rows(
    rows: list[BaseProbabilityRow],
    *,
    min_fusion_train_rows: int,
) -> tuple[list[FusionPredictionRow], tuple[FusionYearResult, ...]]:
    if min_fusion_train_rows <= 0:
        raise ValueError("min_fusion_train_rows must be positive")
    years = sorted({row.year for row in rows})
    predictions: list[FusionPredictionRow] = []
    yearly: list[FusionYearResult] = []

    for test_year in years:
        train = [row for row in rows if row.year < test_year]
        test = [row for row in rows if row.year == test_year]
        if len(train) < min_fusion_train_rows or not test:
            continue
        if len({row.outcome_a for row in train}) < 2:
            continue
        if any(row.year >= test_year for row in train):
            raise RuntimeError("future/non-historical row entered fusion training set")

        outcomes = [row.outcome_a for row in train]
        f1_model = _fit_logistic(_f1_features(train), outcomes)
        f3_model = _fit_logistic(_f3_features(train), outcomes)
        f1_probabilities = f1_model.predict_proba(_f1_features(test))[:, 1].tolist()
        f3_probabilities = f3_model.predict_proba(_f3_features(test))[:, 1].tolist()
        coefficients, intercept = _model_coefficients(f3_model)
        if len(coefficients) != 2:
            raise RuntimeError("two-view fusion model has unexpected coefficient count")

        year_rows = [
            FusionPredictionRow(
                match_id=row.match_id,
                year=row.year,
                outcome_a=row.outcome_a,
                core_control_probability_a=row.core_control_probability_a,
                alignment_probability_a=row.alignment_probability_a,
                f0_alignment_identity=row.alignment_probability_a,
                f1_alignment_recalibration=float(f1_probability),
                f2_equal_logit_blend=_fixed_equal_logit_blend(
                    row.core_control_probability_a,
                    row.alignment_probability_a,
                ),
                f3_two_view_fusion=float(f3_probability),
            )
            for row, f1_probability, f3_probability in zip(
                test,
                f1_probabilities,
                f3_probabilities,
                strict=True,
            )
        ]
        year_comparison = _comparison(year_rows)
        yearly.append(
            FusionYearResult(
                year=test_year,
                n=len(year_rows),
                train_n=len(train),
                f0=year_comparison.f0,
                f1=year_comparison.f1,
                f2=year_comparison.f2,
                f3=year_comparison.f3,
                f3_joint_win_vs_f1=(
                    year_comparison.f3.brier < year_comparison.f1.brier
                    and year_comparison.f3.log_loss < year_comparison.f1.log_loss
                ),
                f3_standardized_core_coefficient=coefficients[0],
                f3_standardized_alignment_coefficient=coefficients[1],
                f3_intercept=intercept,
            )
        )
        predictions.extend(year_rows)

    if not predictions:
        raise ValueError("no chronological fusion predictions are available")
    return predictions, tuple(yearly)


def _recent(rows: list[FusionPredictionRow]) -> list[FusionPredictionRow]:
    return [row for row in rows if _RECENT_START_YEAR <= row.year <= _RECENT_END_YEAR]


def _fusion_gate(
    comparison: FusionComparison,
    recent_comparison: FusionComparison | None,
    yearly: tuple[FusionYearResult, ...],
) -> FusionGate:
    joint_wins = sum(result.f3_joint_win_vs_f1 for result in yearly)
    evaluated = len(yearly)
    win_rate = joint_wins / evaluated if evaluated else 0.0
    recent_brier = (
        None
        if recent_comparison is None
        else recent_comparison.f3.brier <= recent_comparison.f1.brier
    )
    recent_log = (
        None
        if recent_comparison is None
        else recent_comparison.f3.log_loss <= recent_comparison.f1.log_loss
    )
    brier_better = comparison.f3.brier < comparison.f1.brier
    log_better = comparison.f3.log_loss < comparison.f1.log_loss
    passed = bool(
        brier_better
        and log_better
        and win_rate >= 0.60
        and recent_brier is True
        and recent_log is True
    )
    return FusionGate(
        aggregate_brier_better_than_recalibration_control=brier_better,
        aggregate_log_loss_better_than_recalibration_control=log_better,
        joint_year_win_count=joint_wins,
        evaluated_year_count=evaluated,
        joint_year_win_rate=win_rate,
        at_least_60_percent_joint_year_wins=win_rate >= 0.60,
        recent_brier_not_worse=recent_brier,
        recent_log_loss_not_worse=recent_log,
        passed=passed,
    )


def _disagreement_quintiles(
    rows: list[FusionPredictionRow],
) -> tuple[DisagreementQuintile, ...]:
    ordered = sorted(
        rows,
        key=lambda row: (
            abs(row.core_control_probability_a - row.alignment_probability_a),
            row.match_id,
        ),
    )
    total = len(ordered)
    buckets: list[list[FusionPredictionRow]] = [[] for _ in range(5)]
    for rank, row in enumerate(ordered):
        buckets[min((rank * 5) // total, 4)].append(row)

    output: list[DisagreementQuintile] = []
    for index, bucket in enumerate(buckets, start=1):
        if not bucket:
            continue
        outcomes = [row.outcome_a for row in bucket]
        output.append(
            DisagreementQuintile(
                quintile=index,
                n=len(bucket),
                mean_absolute_probability_disagreement=(
                    sum(
                        abs(row.core_control_probability_a - row.alignment_probability_a)
                        for row in bucket
                    )
                    / len(bucket)
                ),
                core_control_brier=brier_score(
                    outcomes,
                    [row.core_control_probability_a for row in bucket],
                ),
                alignment_brier=brier_score(
                    outcomes,
                    [row.alignment_probability_a for row in bucket],
                ),
                fusion_brier=brier_score(
                    outcomes,
                    [row.f3_two_view_fusion for row in bucket],
                ),
            )
        )
    return tuple(output)


def _candidate_probability(row: FusionPredictionRow, candidate: str) -> float:
    mapping = {
        "f0": row.f0_alignment_identity,
        "f1": row.f1_alignment_recalibration,
        "f2": row.f2_equal_logit_blend,
        "f3": row.f3_two_view_fusion,
    }
    try:
        return float(mapping[candidate])
    except KeyError as exc:
        raise ValueError(f"unknown fusion candidate: {candidate!r}") from exc


def _calibration_rows_for_candidate(
    rows: list[FusionPredictionRow],
    *,
    candidate: str,
    min_calibration_rows: int,
) -> tuple[
    dict[str, list[tuple[FusionPredictionRow, float]]],
    dict[str, list[CalibrationYearResult]],
]:
    calibrated: dict[str, list[tuple[FusionPredictionRow, float]]] = {
        name: [] for name in _CALIBRATORS
    }
    yearly: dict[str, list[CalibrationYearResult]] = {name: [] for name in _CALIBRATORS}
    years = sorted({row.year for row in rows})

    for test_year in years:
        prior = [row for row in rows if row.year < test_year]
        current = [row for row in rows if row.year == test_year]
        if len(prior) < min_calibration_rows or not current:
            continue
        outcomes = [row.outcome_a for row in prior]
        if len(set(outcomes)) < 2:
            continue
        prior_probabilities = [_candidate_probability(row, candidate) for row in prior]
        current_probabilities = [_candidate_probability(row, candidate) for row in current]
        current_outcomes = [row.outcome_a for row in current]

        year_predictions: dict[str, list[float]] = {}
        for name in _CALIBRATORS:
            calibrator = make_calibrator(name).fit(prior_probabilities, outcomes)
            probabilities = calibrator.predict(current_probabilities)
            year_predictions[name] = probabilities
            yearly[name].append(
                CalibrationYearResult(
                    year=test_year,
                    n=len(current),
                    train_n=len(prior),
                    score=_score_from_values(current_outcomes, probabilities),
                    joint_win_vs_identity=None,
                )
            )

        identity_score = yearly["identity"][-1].score
        for name in _CALIBRATORS:
            item = yearly[name][-1]
            yearly[name][-1] = CalibrationYearResult(
                year=item.year,
                n=item.n,
                train_n=item.train_n,
                score=item.score,
                joint_win_vs_identity=(
                    None
                    if name == "identity"
                    else item.score.brier < identity_score.brier
                    and item.score.log_loss < identity_score.log_loss
                ),
            )
            calibrated[name].extend(zip(current, year_predictions[name], strict=True))

    return calibrated, yearly


def _calibration_result(
    rows: list[FusionPredictionRow],
    *,
    candidate: str,
    min_calibration_rows: int,
) -> CandidateCalibrationResult:
    calibrated, yearly = _calibration_rows_for_candidate(
        rows,
        candidate=candidate,
        min_calibration_rows=min_calibration_rows,
    )
    identity_rows = calibrated["identity"]
    if not identity_rows:
        raise ValueError(f"no calibration population is available for {candidate}")
    identity_outcomes = [row.outcome_a for row, _ in identity_rows]
    identity_probabilities = [probability for _, probability in identity_rows]
    identity_score = _score_from_values(identity_outcomes, identity_probabilities)
    identity_recent = [
        (row, probability)
        for row, probability in identity_rows
        if _RECENT_START_YEAR <= row.year <= _RECENT_END_YEAR
    ]
    identity_recent_score = (
        _score_from_values(
            [row.outcome_a for row, _ in identity_recent],
            [probability for _, probability in identity_recent],
        )
        if identity_recent
        else None
    )

    methods: list[CalibrationMethodResult] = []
    for name in _CALIBRATORS:
        method_rows = calibrated[name]
        outcomes = [row.outcome_a for row, _ in method_rows]
        probabilities = [probability for _, probability in method_rows]
        score = _score_from_values(outcomes, probabilities)
        recent_rows = [
            (row, probability)
            for row, probability in method_rows
            if _RECENT_START_YEAR <= row.year <= _RECENT_END_YEAR
        ]
        recent_score = (
            _score_from_values(
                [row.outcome_a for row, _ in recent_rows],
                [probability for _, probability in recent_rows],
            )
            if recent_rows
            else None
        )
        joint_wins = sum(result.joint_win_vs_identity is True for result in yearly[name])
        evaluated = len(yearly[name]) if name != "identity" else 0
        win_rate = joint_wins / evaluated if evaluated else 0.0
        brier_improvement = identity_score.brier - score.brier
        log_improvement = identity_score.log_loss - score.log_loss
        ece_change = score.ece_10 - identity_score.ece_10
        if identity_recent_score is None or recent_score is None:
            recent_brier_improvement = None
            recent_log_improvement = None
        else:
            recent_brier_improvement = identity_recent_score.brier - recent_score.brier
            recent_log_improvement = identity_recent_score.log_loss - recent_score.log_loss
        passed = bool(
            name != "identity"
            and brier_improvement > 0.0
            and log_improvement > 0.0
            and ece_change <= 0.002
            and recent_brier_improvement is not None
            and recent_brier_improvement > 0.0
            and recent_log_improvement is not None
            and recent_log_improvement > 0.0
            and win_rate >= 0.60
        )
        methods.append(
            CalibrationMethodResult(
                name=name,
                score=score,
                recent_score=recent_score,
                aggregate_brier_improvement_vs_identity=brier_improvement,
                aggregate_log_loss_improvement_vs_identity=log_improvement,
                aggregate_ece_change_vs_identity=ece_change,
                joint_year_win_count=joint_wins,
                evaluated_year_count=evaluated,
                joint_year_win_rate=win_rate,
                recent_brier_improvement_vs_identity=recent_brier_improvement,
                recent_log_loss_improvement_vs_identity=recent_log_improvement,
                passed_promotion_gate=passed,
                yearly=tuple(yearly[name]),
            )
        )

    passing = [method for method in methods if method.passed_promotion_gate]
    if not passing:
        selected = "identity"
    else:
        passing.sort(
            key=lambda method: (
                method.score.log_loss,
                method.score.brier,
                method.score.ece_10,
                _NON_IDENTITY_TIE_ORDER[method.name],
            )
        )
        selected = passing[0].name

    return CandidateCalibrationResult(
        candidate=candidate,
        population_n=len(identity_rows),
        selected_calibrator=selected,
        methods=tuple(methods),
    )


def run_fusion_calibration(
    matches: list[HistoricalMatch],
    *,
    tour: Tour,
    min_core_train_matches: int = 1000,
    min_neighbor_pool: int = 1000,
    min_meta_train_rows: int = 1000,
    min_fusion_train_rows: int = 1000,
    min_calibration_rows: int = 1000,
    exclude_retirements: bool = True,
) -> FusionCalibrationReport:
    for name, value in (
        ("min_core_train_matches", min_core_train_matches),
        ("min_neighbor_pool", min_neighbor_pool),
        ("min_meta_train_rows", min_meta_train_rows),
        ("min_fusion_train_rows", min_fusion_train_rows),
        ("min_calibration_rows", min_calibration_rows),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive")

    base_rows = _base_probability_rows(
        matches,
        tour=tour,
        min_core_train_matches=min_core_train_matches,
        min_neighbor_pool=min_neighbor_pool,
        min_meta_train_rows=min_meta_train_rows,
        exclude_retirements=exclude_retirements,
    )
    predictions, yearly = _fusion_oof_from_base_rows(
        base_rows,
        min_fusion_train_rows=min_fusion_train_rows,
    )
    comparison = _comparison(predictions)
    recent_rows = _recent(predictions)
    recent_comparison = _comparison(recent_rows) if recent_rows else None
    gate = _fusion_gate(comparison, recent_comparison, yearly)

    calibration = tuple(
        _calibration_result(
            predictions,
            candidate=candidate,
            min_calibration_rows=min_calibration_rows,
        )
        for candidate in ("f0", "f1", "f2", "f3")
    )
    selected_candidate = "f3" if gate.passed else "f0"
    selected_calibration = next(
        result for result in calibration if result.candidate == selected_candidate
    )
    alignment_representation = "full_genome" if tour == "ATP" else "strict_core_geometry"
    decision = ArchitectureDecision(
        fusion_promoted=gate.passed,
        selected_probability_candidate=selected_candidate,
        selected_calibrator=selected_calibration.selected_calibrator,
        note=(
            "two-view fusion passed all preregistered gates"
            if gate.passed
            else (
                "two-view fusion failed at least one preregistered gate; retain incumbent alignment"
            )
        ),
    )

    return FusionCalibrationReport(
        experiment_id="FUSION-CAL-001",
        tour=tour,
        development_end_year=_DEVELOPMENT_END_YEAR,
        alignment_representation=alignment_representation,
        min_core_train_matches=min_core_train_matches,
        min_neighbor_pool=min_neighbor_pool,
        min_meta_train_rows=min_meta_train_rows,
        min_fusion_train_rows=min_fusion_train_rows,
        min_calibration_rows=min_calibration_rows,
        base_population_n=len(base_rows),
        fusion_population_n=len(predictions),
        comparison=comparison,
        recent_comparison=recent_comparison,
        yearly=yearly,
        fusion_gate=gate,
        disagreement_quintiles=_disagreement_quintiles(predictions),
        calibration=calibration,
        architecture_decision=decision,
        predictions=tuple(predictions),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run preregistered FUSION-CAL-001 on frozen development data"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--tour", required=True, choices=("ATP", "WTA"))
    parser.add_argument("--min-core-train-matches", type=int, default=1000)
    parser.add_argument("--min-neighbor-pool", type=int, default=1000)
    parser.add_argument("--min-meta-train-rows", type=int, default=1000)
    parser.add_argument("--min-fusion-train-rows", type=int, default=1000)
    parser.add_argument("--min-calibration-rows", type=int, default=1000)
    parser.add_argument("--include-retirements", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    verify_canonical_manifest(
        manifest_path=args.manifest,
        pre_match_path=args.pre_match,
        outcome_path=args.outcomes,
        stats_path=args.stats,
        require_research_permission=True,
    )
    matches = load_canonical_parquet(
        pre_match_path=args.pre_match,
        outcome_path=args.outcomes,
        stats_path=args.stats,
    )
    report = run_fusion_calibration(
        matches,
        tour=args.tour,
        min_core_train_matches=args.min_core_train_matches,
        min_neighbor_pool=args.min_neighbor_pool,
        min_meta_train_rows=args.min_meta_train_rows,
        min_fusion_train_rows=args.min_fusion_train_rows,
        min_calibration_rows=args.min_calibration_rows,
        exclude_retirements=not args.include_retirements,
    )
    print(json.dumps(asdict(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
