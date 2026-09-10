from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from tennis_genome.data.canonical import HistoricalMatch
from tennis_genome.data.manifest import verify_canonical_manifest
from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.evaluation.metrics import (
    accuracy,
    binary_log_loss,
    brier_score,
    expected_calibration_error,
)
from tennis_genome.experiments.genome_adversarial_controls import (
    run_genome_adversarial_controls,
)
from tennis_genome.experiments.pointsim import run_pointsim

_DEVELOPMENT_END_YEAR = 2025
_RECENT_START_YEAR = 2021
_RECENT_END_YEAR = 2025


@dataclass(frozen=True)
class Score:
    n: int
    brier: float
    log_loss: float
    accuracy: float
    ece_10: float


@dataclass(frozen=True)
class MatchedRow:
    match_id: str
    year: int
    outcome_a: bool
    alignment_probability_a: float
    pointsim_probability_a: float


@dataclass(frozen=True)
class PredictionRow:
    match_id: str
    year: int
    outcome_a: bool
    alignment_probability_a: float
    pointsim_probability_a: float
    alignment_recalibration_probability_a: float
    alignment_plus_pointsim_probability_a: float


@dataclass(frozen=True)
class YearResult:
    year: int
    n: int
    train_n: int
    control: Score
    challenger: Score
    challenger_joint_win: bool
    standardized_alignment_coefficient: float
    standardized_pointsim_coefficient: float
    intercept: float


@dataclass(frozen=True)
class GateResult:
    aggregate_brier_better: bool
    aggregate_log_loss_better: bool
    joint_year_win_count: int
    evaluated_year_count: int
    joint_year_win_rate: float
    at_least_60_percent_joint_year_wins: bool
    recent_brier_not_worse: bool | None
    recent_log_loss_not_worse: bool | None
    passed: bool


@dataclass(frozen=True)
class Comparison:
    n: int
    incumbent_alignment: Score
    alignment_recalibration_control: Score
    alignment_plus_pointsim: Score
    challenger_vs_control_brier_improvement: float
    challenger_vs_control_log_loss_improvement: float


@dataclass(frozen=True)
class PointSimAdversarialReport:
    experiment_id: str
    tour: str
    development_end_year: int
    min_core_train_matches: int
    min_neighbor_pool: int
    min_meta_train_rows: int
    min_pointsim_train_rows: int
    min_adversary_train_rows: int
    matched_population_n: int
    prediction_population_n: int
    comparison: Comparison
    recent_comparison: Comparison | None
    gate: GateResult
    yearly: tuple[YearResult, ...]
    predictions: tuple[PredictionRow, ...]


def _clip_probability(value: float) -> float:
    return min(max(float(value), 1e-9), 1.0 - 1e-9)


def _logit(value: float) -> float:
    p = _clip_probability(value)
    return math.log(p / (1.0 - p))


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


def _score(rows: list[PredictionRow], field: str) -> Score:
    return _score_from_values(
        [row.outcome_a for row in rows],
        [float(getattr(row, field)) for row in rows],
    )


def _fit_logistic(matrix: list[list[float]], outcomes: list[bool]) -> Pipeline:
    if not matrix or len(matrix) != len(outcomes):
        raise ValueError("fit inputs must have equal non-zero length")
    if len(set(outcomes)) < 2:
        raise ValueError("fit requires both outcome classes")
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000),
    )
    model.fit(matrix, [int(value) for value in outcomes])
    return model


def _control_features(rows: list[MatchedRow]) -> list[list[float]]:
    return [[_logit(row.alignment_probability_a)] for row in rows]


def _challenger_features(rows: list[MatchedRow]) -> list[list[float]]:
    return [
        [
            _logit(row.alignment_probability_a),
            _logit(row.pointsim_probability_a),
        ]
        for row in rows
    ]


def _model_coefficients(model: Pipeline) -> tuple[list[float], float]:
    logistic = model[-1]
    return logistic.coef_[0].astype(float).tolist(), float(logistic.intercept_[0])


def _build_matched_rows(
    matches: list[HistoricalMatch],
    *,
    min_core_train_matches: int,
    min_neighbor_pool: int,
    min_meta_train_rows: int,
    min_pointsim_train_rows: int,
    exclude_retirements: bool,
) -> list[MatchedRow]:
    selected = [match for match in matches if match.pre_match.tour == "WTA"]
    if any(match.pre_match.event_date.year > _DEVELOPMENT_END_YEAR for match in selected):
        raise ValueError("post-2025 WTA data are forbidden in POINTSIM-ADV-001")

    alignment = run_genome_adversarial_controls(
        matches,
        tour="WTA",
        min_core_train_matches=min_core_train_matches,
        min_neighbor_pool=min_neighbor_pool,
        min_meta_train_rows=min_meta_train_rows,
        exclude_retirements=exclude_retirements,
    )
    pointsim = run_pointsim(
        matches,
        tour="WTA",
        min_core_train_matches=min_core_train_matches,
        min_model_train_rows=min_pointsim_train_rows,
        exclude_retirements=exclude_retirements,
    )

    alignment_by_id = {row.match_id: row for row in alignment.predictions}
    pointsim_by_id = {row.match_id: row for row in pointsim.predictions}
    if len(alignment_by_id) != len(alignment.predictions):
        raise RuntimeError("duplicate WTA alignment match_id")
    if len(pointsim_by_id) != len(pointsim.predictions):
        raise RuntimeError("duplicate WTA POINTSIM match_id")

    common_ids = sorted(set(alignment_by_id) & set(pointsim_by_id))
    rows: list[MatchedRow] = []
    for match_id in common_ids:
        alignment_row = alignment_by_id[match_id]
        pointsim_row = pointsim_by_id[match_id]
        if alignment_row.year != pointsim_row.year:
            raise RuntimeError(f"year mismatch for {match_id}")
        if alignment_row.outcome_a != pointsim_row.outcome_a:
            raise RuntimeError(f"outcome mismatch for {match_id}")
        rows.append(
            MatchedRow(
                match_id=match_id,
                year=alignment_row.year,
                outcome_a=alignment_row.outcome_a,
                alignment_probability_a=alignment_row.core_neighborhood_probability_a,
                pointsim_probability_a=pointsim_row.pointsim_probability_a,
            )
        )
    if not rows:
        raise ValueError("no matched WTA POINTSIM-adversarial rows are available")
    return sorted(rows, key=lambda row: (row.year, row.match_id))


def _walk_forward(
    rows: list[MatchedRow],
    *,
    min_adversary_train_rows: int,
) -> tuple[list[PredictionRow], tuple[YearResult, ...]]:
    if min_adversary_train_rows <= 0:
        raise ValueError("min_adversary_train_rows must be positive")
    predictions: list[PredictionRow] = []
    yearly: list[YearResult] = []
    for test_year in sorted({row.year for row in rows}):
        train = [row for row in rows if row.year < test_year]
        test = [row for row in rows if row.year == test_year]
        if len(train) < min_adversary_train_rows or not test:
            continue
        if any(row.year >= test_year for row in train):
            raise RuntimeError("future row entered POINTSIM-ADV-001 training set")
        outcomes = [row.outcome_a for row in train]
        if len(set(outcomes)) < 2:
            continue

        control_model = _fit_logistic(_control_features(train), outcomes)
        challenger_model = _fit_logistic(_challenger_features(train), outcomes)
        control_p = control_model.predict_proba(_control_features(test))[:, 1].tolist()
        challenger_p = challenger_model.predict_proba(_challenger_features(test))[:, 1].tolist()
        coefficients, intercept = _model_coefficients(challenger_model)
        if len(coefficients) != 2:
            raise RuntimeError("POINTSIM adversarial model has unexpected coefficient count")

        year_rows = [
            PredictionRow(
                match_id=row.match_id,
                year=row.year,
                outcome_a=row.outcome_a,
                alignment_probability_a=row.alignment_probability_a,
                pointsim_probability_a=row.pointsim_probability_a,
                alignment_recalibration_probability_a=float(control_probability),
                alignment_plus_pointsim_probability_a=float(challenger_probability),
            )
            for row, control_probability, challenger_probability in zip(
                test,
                control_p,
                challenger_p,
                strict=True,
            )
        ]
        control_score = _score(year_rows, "alignment_recalibration_probability_a")
        challenger_score = _score(year_rows, "alignment_plus_pointsim_probability_a")
        yearly.append(
            YearResult(
                year=test_year,
                n=len(year_rows),
                train_n=len(train),
                control=control_score,
                challenger=challenger_score,
                challenger_joint_win=(
                    challenger_score.brier < control_score.brier
                    and challenger_score.log_loss < control_score.log_loss
                ),
                standardized_alignment_coefficient=coefficients[0],
                standardized_pointsim_coefficient=coefficients[1],
                intercept=intercept,
            )
        )
        predictions.extend(year_rows)
    if not predictions:
        raise ValueError("no chronological POINTSIM-ADV-001 predictions are available")
    return predictions, tuple(yearly)


def _comparison(rows: list[PredictionRow]) -> Comparison:
    incumbent = _score(rows, "alignment_probability_a")
    control = _score(rows, "alignment_recalibration_probability_a")
    challenger = _score(rows, "alignment_plus_pointsim_probability_a")
    return Comparison(
        n=len(rows),
        incumbent_alignment=incumbent,
        alignment_recalibration_control=control,
        alignment_plus_pointsim=challenger,
        challenger_vs_control_brier_improvement=control.brier - challenger.brier,
        challenger_vs_control_log_loss_improvement=control.log_loss - challenger.log_loss,
    )


def _recent(rows: list[PredictionRow]) -> list[PredictionRow]:
    return [
        row
        for row in rows
        if _RECENT_START_YEAR <= row.year <= _RECENT_END_YEAR
    ]


def _gate(
    comparison: Comparison,
    recent_comparison: Comparison | None,
    yearly: tuple[YearResult, ...],
) -> GateResult:
    wins = sum(item.challenger_joint_win for item in yearly)
    evaluated = len(yearly)
    win_rate = wins / evaluated if evaluated else 0.0
    recent_brier = (
        None
        if recent_comparison is None
        else recent_comparison.alignment_plus_pointsim.brier
        <= recent_comparison.alignment_recalibration_control.brier
    )
    recent_log = (
        None
        if recent_comparison is None
        else recent_comparison.alignment_plus_pointsim.log_loss
        <= recent_comparison.alignment_recalibration_control.log_loss
    )
    brier_better = comparison.challenger_vs_control_brier_improvement > 0.0
    log_better = comparison.challenger_vs_control_log_loss_improvement > 0.0
    passed = bool(
        brier_better
        and log_better
        and win_rate >= 0.60
        and recent_brier is True
        and recent_log is True
    )
    return GateResult(
        aggregate_brier_better=brier_better,
        aggregate_log_loss_better=log_better,
        joint_year_win_count=wins,
        evaluated_year_count=evaluated,
        joint_year_win_rate=win_rate,
        at_least_60_percent_joint_year_wins=win_rate >= 0.60,
        recent_brier_not_worse=recent_brier,
        recent_log_loss_not_worse=recent_log,
        passed=passed,
    )


def run_pointsim_adversarial(
    matches: list[HistoricalMatch],
    *,
    min_core_train_matches: int = 1000,
    min_neighbor_pool: int = 1000,
    min_meta_train_rows: int = 1000,
    min_pointsim_train_rows: int = 1000,
    min_adversary_train_rows: int = 1000,
    exclude_retirements: bool = True,
) -> PointSimAdversarialReport:
    rows = _build_matched_rows(
        matches,
        min_core_train_matches=min_core_train_matches,
        min_neighbor_pool=min_neighbor_pool,
        min_meta_train_rows=min_meta_train_rows,
        min_pointsim_train_rows=min_pointsim_train_rows,
        exclude_retirements=exclude_retirements,
    )
    predictions, yearly = _walk_forward(
        rows,
        min_adversary_train_rows=min_adversary_train_rows,
    )
    comparison = _comparison(predictions)
    recent_rows = _recent(predictions)
    recent_comparison = _comparison(recent_rows) if recent_rows else None
    return PointSimAdversarialReport(
        experiment_id="POINTSIM-ADV-001",
        tour="WTA",
        development_end_year=_DEVELOPMENT_END_YEAR,
        min_core_train_matches=min_core_train_matches,
        min_neighbor_pool=min_neighbor_pool,
        min_meta_train_rows=min_meta_train_rows,
        min_pointsim_train_rows=min_pointsim_train_rows,
        min_adversary_train_rows=min_adversary_train_rows,
        matched_population_n=len(rows),
        prediction_population_n=len(predictions),
        comparison=comparison,
        recent_comparison=recent_comparison,
        gate=_gate(comparison, recent_comparison, yearly),
        yearly=yearly,
        predictions=tuple(predictions),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run WTA POINTSIM-ADV-001 on frozen 2000-2025 development data"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--min-core-train-matches", type=int, default=1000)
    parser.add_argument("--min-neighbor-pool", type=int, default=1000)
    parser.add_argument("--min-meta-train-rows", type=int, default=1000)
    parser.add_argument("--min-pointsim-train-rows", type=int, default=1000)
    parser.add_argument("--min-adversary-train-rows", type=int, default=1000)
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
    report = run_pointsim_adversarial(
        matches,
        min_core_train_matches=args.min_core_train_matches,
        min_neighbor_pool=args.min_neighbor_pool,
        min_meta_train_rows=args.min_meta_train_rows,
        min_pointsim_train_rows=args.min_pointsim_train_rows,
        min_adversary_train_rows=args.min_adversary_train_rows,
        exclude_retirements=not args.include_retirements,
    )
    print(json.dumps(asdict(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
