from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from tennis_genome.data.canonical import HistoricalMatch, Tour
from tennis_genome.data.manifest import verify_canonical_manifest
from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.evaluation.metrics import (
    accuracy,
    binary_log_loss,
    brier_score,
    expected_calibration_error,
)
from tennis_genome.experiments.genome_neighborhood import _build_core_ledger
from tennis_genome.ratings.serve_return import walk_forward_serve_return
from tennis_genome.simulation.tennis import point_sim_match_probability

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
class BaseRow:
    match_id: str
    year: int
    outcome_a: bool
    best_of: int
    p_a_serve: float
    p_b_serve: float
    pointsim_probability_a: float
    core_probability_a: float
    min_prior_point_history: int


@dataclass(frozen=True)
class PredictionRow:
    match_id: str
    year: int
    outcome_a: bool
    best_of: int
    p_a_serve: float
    p_b_serve: float
    pointsim_probability_a: float
    same_input_control_probability_a: float
    core_control_probability_a: float
    core_plus_pointsim_probability_a: float
    min_prior_point_history: int


@dataclass(frozen=True)
class YearResult:
    year: int
    n: int
    train_n: int
    same_input_control: Score
    pointsim: Score
    core_control: Score
    core_plus_pointsim: Score
    mechanics_joint_win: bool
    incremental_joint_win: bool


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
class FormatDiagnostic:
    best_of: int
    n: int
    same_input_control: Score
    pointsim: Score
    core_control: Score
    core_plus_pointsim: Score


@dataclass(frozen=True)
class HistoryDiagnostic:
    minimum_prior_points: int
    n: int
    same_input_control: Score
    pointsim: Score
    core_control: Score
    core_plus_pointsim: Score


@dataclass(frozen=True)
class PointSimReport:
    experiment_id: str
    tour: Tour
    development_end_year: int
    min_core_train_matches: int
    min_model_train_rows: int
    eligible_population_n: int
    supported_format_population_n: int
    supported_format_coverage: float
    oof_population_n: int
    same_input_control: Score
    pointsim: Score
    core_control: Score
    core_plus_pointsim: Score
    recent_same_input_control: Score | None
    recent_pointsim: Score | None
    recent_core_control: Score | None
    recent_core_plus_pointsim: Score | None
    mechanics_gate: GateResult
    incremental_gate: GateResult
    yearly: tuple[YearResult, ...]
    format_diagnostics: tuple[FormatDiagnostic, ...]
    history_diagnostics: tuple[HistoryDiagnostic, ...]
    predictions: tuple[PredictionRow, ...]


def _clip_probability(value: float) -> float:
    return min(max(float(value), 1e-9), 1.0 - 1e-9)


def _logit(value: float) -> float:
    probability = _clip_probability(value)
    return math.log(probability / (1.0 - probability))


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


def _eligible_matches(
    matches: list[HistoricalMatch],
    *,
    tour: Tour,
    exclude_retirements: bool,
) -> list[HistoricalMatch]:
    tour_matches = [match for match in matches if match.pre_match.tour == tour]
    if any(match.pre_match.event_date.year > _DEVELOPMENT_END_YEAR for match in tour_matches):
        raise ValueError(
            "POINTSIM-001 is frozen to 2000-2025 development data; post-2025 "
            "selected-tour rows are forbidden"
        )
    return [
        match
        for match in tour_matches
        if not match.outcome.walkover
        and (not exclude_retirements or not match.outcome.retirement)
    ]


def _build_base_rows(
    eligible: list[HistoricalMatch],
    *,
    tour: Tour,
    min_core_train_matches: int,
) -> tuple[list[BaseRow], int]:
    core = {
        row.match_id: row
        for row in _build_core_ledger(
            eligible,
            tour=tour,
            min_core_train_matches=min_core_train_matches,
        )
    }
    serve_return = {
        row.match_id: row
        for row in walk_forward_serve_return(
            eligible,
            exclude_retirements=False,
        )
    }
    matches_by_id = {match.match_id: match for match in eligible}
    available_ids = set(core) & set(serve_return) & set(matches_by_id)
    supported_ids = [
        match_id
        for match_id in available_ids
        if matches_by_id[match_id].pre_match.best_of in (3, 5)
    ]

    rows: list[BaseRow] = []
    for match_id in supported_ids:
        match = matches_by_id[match_id]
        snapshot = serve_return[match_id]
        core_row = core[match_id]
        best_of = match.pre_match.best_of
        if best_of not in (3, 5):
            raise RuntimeError("unsupported best_of escaped POINTSIM population filter")
        rows.append(
            BaseRow(
                match_id=match_id,
                year=match.pre_match.event_date.year,
                outcome_a=match.outcome.a_won,
                best_of=best_of,
                p_a_serve=snapshot.probability_a_serve_point,
                p_b_serve=snapshot.probability_b_serve_point,
                pointsim_probability_a=point_sim_match_probability(
                    snapshot.probability_a_serve_point,
                    snapshot.probability_b_serve_point,
                    best_of=best_of,
                ),
                core_probability_a=core_row.core_probability_a,
                min_prior_point_history=min(
                    snapshot.prior_serve_points_a,
                    snapshot.prior_serve_points_b,
                    snapshot.prior_return_points_a,
                    snapshot.prior_return_points_b,
                ),
            )
        )
    return sorted(rows, key=lambda row: (row.year, row.match_id)), len(available_ids)


def _fit_logistic(matrix: list[list[float]], outcomes: list[bool]):
    if not matrix or len(matrix) != len(outcomes):
        raise ValueError("model fit inputs must have equal non-zero length")
    if len(set(outcomes)) < 2:
        raise ValueError("model fit requires both outcome classes")
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000),
    )
    model.fit(matrix, [int(value) for value in outcomes])
    return model


def _same_input_features(rows: list[BaseRow]) -> list[list[float]]:
    return [
        [
            _logit(row.p_a_serve),
            _logit(row.p_b_serve),
            1.0 if row.best_of == 5 else 0.0,
        ]
        for row in rows
    ]


def _core_features(rows: list[BaseRow]) -> list[list[float]]:
    return [[_logit(row.core_probability_a)] for row in rows]


def _incremental_features(rows: list[BaseRow]) -> list[list[float]]:
    return [
        [
            _logit(row.core_probability_a),
            _logit(row.pointsim_probability_a),
        ]
        for row in rows
    ]


def _walk_forward_predictions(
    rows: list[BaseRow],
    *,
    min_model_train_rows: int,
) -> tuple[list[PredictionRow], tuple[YearResult, ...]]:
    if min_model_train_rows <= 0:
        raise ValueError("min_model_train_rows must be positive")
    years = sorted({row.year for row in rows})
    predictions: list[PredictionRow] = []
    yearly: list[YearResult] = []

    for test_year in years:
        train = [row for row in rows if row.year < test_year]
        test = [row for row in rows if row.year == test_year]
        if len(train) < min_model_train_rows or not test:
            continue
        if any(row.year >= test_year for row in train):
            raise RuntimeError("future/non-historical row entered POINTSIM training set")

        outcomes = [row.outcome_a for row in train]
        if len(set(outcomes)) < 2:
            continue
        same_input_model = _fit_logistic(_same_input_features(train), outcomes)
        core_model = _fit_logistic(_core_features(train), outcomes)
        incremental_model = _fit_logistic(_incremental_features(train), outcomes)

        s0 = same_input_model.predict_proba(_same_input_features(test))[:, 1].tolist()
        m0 = core_model.predict_proba(_core_features(test))[:, 1].tolist()
        m1 = incremental_model.predict_proba(_incremental_features(test))[:, 1].tolist()
        year_rows = [
            PredictionRow(
                match_id=row.match_id,
                year=row.year,
                outcome_a=row.outcome_a,
                best_of=row.best_of,
                p_a_serve=row.p_a_serve,
                p_b_serve=row.p_b_serve,
                pointsim_probability_a=row.pointsim_probability_a,
                same_input_control_probability_a=float(s0_probability),
                core_control_probability_a=float(m0_probability),
                core_plus_pointsim_probability_a=float(m1_probability),
                min_prior_point_history=row.min_prior_point_history,
            )
            for row, s0_probability, m0_probability, m1_probability in zip(
                test,
                s0,
                m0,
                m1,
                strict=True,
            )
        ]
        s0_score = _score(year_rows, "same_input_control_probability_a")
        s1_score = _score(year_rows, "pointsim_probability_a")
        m0_score = _score(year_rows, "core_control_probability_a")
        m1_score = _score(year_rows, "core_plus_pointsim_probability_a")
        yearly.append(
            YearResult(
                year=test_year,
                n=len(year_rows),
                train_n=len(train),
                same_input_control=s0_score,
                pointsim=s1_score,
                core_control=m0_score,
                core_plus_pointsim=m1_score,
                mechanics_joint_win=(
                    s1_score.brier < s0_score.brier
                    and s1_score.log_loss < s0_score.log_loss
                ),
                incremental_joint_win=(
                    m1_score.brier < m0_score.brier
                    and m1_score.log_loss < m0_score.log_loss
                ),
            )
        )
        predictions.extend(year_rows)

    if not predictions:
        raise ValueError("no chronological POINTSIM predictions are available")
    return predictions, tuple(yearly)


def _recent(rows: list[PredictionRow]) -> list[PredictionRow]:
    return [
        row
        for row in rows
        if _RECENT_START_YEAR <= row.year <= _RECENT_END_YEAR
    ]


def _gate(
    *,
    control: Score,
    challenger: Score,
    recent_control: Score | None,
    recent_challenger: Score | None,
    yearly: tuple[YearResult, ...],
    joint_field: str,
) -> GateResult:
    wins = sum(bool(getattr(item, joint_field)) for item in yearly)
    evaluated = len(yearly)
    win_rate = wins / evaluated if evaluated else 0.0
    recent_brier = (
        None
        if recent_control is None or recent_challenger is None
        else recent_challenger.brier <= recent_control.brier
    )
    recent_log = (
        None
        if recent_control is None or recent_challenger is None
        else recent_challenger.log_loss <= recent_control.log_loss
    )
    brier_better = challenger.brier < control.brier
    log_better = challenger.log_loss < control.log_loss
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


def _format_diagnostics(rows: list[PredictionRow]) -> tuple[FormatDiagnostic, ...]:
    output: list[FormatDiagnostic] = []
    for best_of in (3, 5):
        subset = [row for row in rows if row.best_of == best_of]
        if not subset:
            continue
        output.append(
            FormatDiagnostic(
                best_of=best_of,
                n=len(subset),
                same_input_control=_score(subset, "same_input_control_probability_a"),
                pointsim=_score(subset, "pointsim_probability_a"),
                core_control=_score(subset, "core_control_probability_a"),
                core_plus_pointsim=_score(subset, "core_plus_pointsim_probability_a"),
            )
        )
    return tuple(output)


def _history_diagnostics(rows: list[PredictionRow]) -> tuple[HistoryDiagnostic, ...]:
    output: list[HistoryDiagnostic] = []
    for threshold in (0, 250, 1000):
        subset = [row for row in rows if row.min_prior_point_history >= threshold]
        if not subset:
            continue
        output.append(
            HistoryDiagnostic(
                minimum_prior_points=threshold,
                n=len(subset),
                same_input_control=_score(subset, "same_input_control_probability_a"),
                pointsim=_score(subset, "pointsim_probability_a"),
                core_control=_score(subset, "core_control_probability_a"),
                core_plus_pointsim=_score(subset, "core_plus_pointsim_probability_a"),
            )
        )
    return tuple(output)


def run_pointsim(
    matches: list[HistoricalMatch],
    *,
    tour: Tour,
    min_core_train_matches: int = 1000,
    min_model_train_rows: int = 1000,
    exclude_retirements: bool = True,
) -> PointSimReport:
    """Run preregistered POINTSIM-001 on a chronological matched population."""
    if min_core_train_matches <= 0 or min_model_train_rows <= 0:
        raise ValueError("minimum training populations must be positive")
    eligible = _eligible_matches(
        matches,
        tour=tour,
        exclude_retirements=exclude_retirements,
    )
    base_rows, available_n = _build_base_rows(
        eligible,
        tour=tour,
        min_core_train_matches=min_core_train_matches,
    )
    if not base_rows:
        raise ValueError("no supported-format POINTSIM rows are available")
    predictions, yearly = _walk_forward_predictions(
        base_rows,
        min_model_train_rows=min_model_train_rows,
    )

    s0 = _score(predictions, "same_input_control_probability_a")
    s1 = _score(predictions, "pointsim_probability_a")
    m0 = _score(predictions, "core_control_probability_a")
    m1 = _score(predictions, "core_plus_pointsim_probability_a")
    recent = _recent(predictions)
    recent_s0 = _score(recent, "same_input_control_probability_a") if recent else None
    recent_s1 = _score(recent, "pointsim_probability_a") if recent else None
    recent_m0 = _score(recent, "core_control_probability_a") if recent else None
    recent_m1 = _score(recent, "core_plus_pointsim_probability_a") if recent else None

    mechanics_gate = _gate(
        control=s0,
        challenger=s1,
        recent_control=recent_s0,
        recent_challenger=recent_s1,
        yearly=yearly,
        joint_field="mechanics_joint_win",
    )
    incremental_gate = _gate(
        control=m0,
        challenger=m1,
        recent_control=recent_m0,
        recent_challenger=recent_m1,
        yearly=yearly,
        joint_field="incremental_joint_win",
    )

    return PointSimReport(
        experiment_id="POINTSIM-001",
        tour=tour,
        development_end_year=_DEVELOPMENT_END_YEAR,
        min_core_train_matches=min_core_train_matches,
        min_model_train_rows=min_model_train_rows,
        eligible_population_n=len(eligible),
        supported_format_population_n=len(base_rows),
        supported_format_coverage=(len(base_rows) / available_n if available_n else 0.0),
        oof_population_n=len(predictions),
        same_input_control=s0,
        pointsim=s1,
        core_control=m0,
        core_plus_pointsim=m1,
        recent_same_input_control=recent_s0,
        recent_pointsim=recent_s1,
        recent_core_control=recent_m0,
        recent_core_plus_pointsim=recent_m1,
        mechanics_gate=mechanics_gate,
        incremental_gate=incremental_gate,
        yearly=yearly,
        format_diagnostics=_format_diagnostics(predictions),
        history_diagnostics=_history_diagnostics(predictions),
        predictions=tuple(predictions),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run POINTSIM-001 on frozen 2000-2025 development data"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--tour", required=True, choices=("ATP", "WTA"))
    parser.add_argument("--min-core-train-matches", type=int, default=1000)
    parser.add_argument("--min-model-train-rows", type=int, default=1000)
    parser.add_argument(
        "--include-retirements",
        action="store_true",
        help="Include retirements; walkovers remain excluded",
    )
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
    report = run_pointsim(
        matches,
        tour=args.tour,
        min_core_train_matches=args.min_core_train_matches,
        min_model_train_rows=args.min_model_train_rows,
        exclude_retirements=not args.include_retirements,
    )
    print(json.dumps(asdict(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
