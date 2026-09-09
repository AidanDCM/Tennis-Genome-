from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from math import log
from pathlib import Path

from sklearn.linear_model import LogisticRegression

from tennis_genome.data.canonical import HistoricalMatch
from tennis_genome.data.manifest import verify_canonical_manifest
from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.evaluation.metrics import (
    accuracy,
    binary_log_loss,
    brier_score,
    expected_calibration_error,
)
from tennis_genome.evaluation.walkforward import walk_forward_elo
from tennis_genome.ratings.serve_return import (
    ServeReturnConfig,
    ServeReturnSnapshot,
    walk_forward_serve_return,
)


@dataclass(frozen=True)
class ModelScore:
    n: int
    brier: float
    log_loss: float
    accuracy: float
    ece_10: float


@dataclass(frozen=True)
class PeriodComparison:
    year: int
    n: int
    elo_calibrated: ModelScore
    elo_serve_return: ModelScore
    brier_improvement: float
    log_loss_improvement: float
    accuracy_change: float


@dataclass(frozen=True)
class HistorySlice:
    min_prior_points: int
    n: int
    elo_calibrated: ModelScore
    elo_serve_return: ModelScore
    brier_improvement: float
    log_loss_improvement: float
    accuracy_change: float


@dataclass(frozen=True)
class Exp003Report:
    experiment_id: str
    population_n: int
    min_train_matches: int
    serve_return_config: ServeReturnConfig
    elo_calibrated: ModelScore
    elo_serve_return: ModelScore
    brier_improvement: float
    log_loss_improvement: float
    accuracy_change: float
    yearly: tuple[PeriodComparison, ...]
    history_slices: tuple[HistorySlice, ...]


@dataclass(frozen=True)
class _FeatureRow:
    match_id: str
    year: int
    outcome_a: bool
    elo_logit: float
    serve_return_edge: float
    min_prior_points: int


def _score(y_true: list[bool], probabilities: list[float]) -> ModelScore:
    return ModelScore(
        n=len(y_true),
        brier=brier_score(y_true, probabilities),
        log_loss=binary_log_loss(y_true, probabilities),
        accuracy=accuracy(y_true, probabilities),
        ece_10=expected_calibration_error(y_true, probabilities, n_bins=10),
    )


def _logit_probability(probability: float) -> float:
    clipped = min(max(probability, 1e-9), 1.0 - 1e-9)
    return log(clipped / (1.0 - clipped))


def _feature_rows(
    matches: list[HistoricalMatch],
    *,
    config: ServeReturnConfig,
    exclude_retirements: bool,
) -> list[_FeatureRow]:
    elo = {
        prediction.match_id: prediction
        for prediction in walk_forward_elo(
            matches,
            exclude_retirements=exclude_retirements,
        )
    }
    serve_return = {
        snapshot.match_id: snapshot
        for snapshot in walk_forward_serve_return(
            matches,
            config=config,
            exclude_retirements=exclude_retirements,
        )
    }
    outcomes = {match.match_id: match.outcome.a_won for match in matches}

    rows: list[_FeatureRow] = []
    for match_id in sorted(
        set(elo).intersection(serve_return),
        key=lambda value: (elo[value].event_date, value),
    ):
        snapshot: ServeReturnSnapshot = serve_return[match_id]
        min_prior_points = min(
            snapshot.prior_serve_points_a,
            snapshot.prior_serve_points_b,
            snapshot.prior_return_points_a,
            snapshot.prior_return_points_b,
        )
        rows.append(
            _FeatureRow(
                match_id=match_id,
                year=elo[match_id].event_date.year,
                outcome_a=outcomes[match_id],
                elo_logit=_logit_probability(elo[match_id].probability_a),
                serve_return_edge=snapshot.matchup_edge_a,
                min_prior_points=min_prior_points,
            )
        )
    return rows


def _predict_year(
    train: list[_FeatureRow],
    test: list[_FeatureRow],
) -> tuple[list[float], list[float]]:
    y_train = [int(row.outcome_a) for row in train]
    baseline = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
    challenger = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
    baseline.fit([[row.elo_logit] for row in train], y_train)
    challenger.fit(
        [[row.elo_logit, row.serve_return_edge] for row in train],
        y_train,
    )
    baseline_probs = baseline.predict_proba(
        [[row.elo_logit] for row in test]
    )[:, 1].tolist()
    challenger_probs = challenger.predict_proba(
        [[row.elo_logit, row.serve_return_edge] for row in test]
    )[:, 1].tolist()
    return baseline_probs, challenger_probs


def _comparison(
    *,
    year: int,
    y_true: list[bool],
    baseline_probs: list[float],
    challenger_probs: list[float],
) -> PeriodComparison:
    baseline_score = _score(y_true, baseline_probs)
    challenger_score = _score(y_true, challenger_probs)
    return PeriodComparison(
        year=year,
        n=len(y_true),
        elo_calibrated=baseline_score,
        elo_serve_return=challenger_score,
        brier_improvement=baseline_score.brier - challenger_score.brier,
        log_loss_improvement=baseline_score.log_loss - challenger_score.log_loss,
        accuracy_change=challenger_score.accuracy - baseline_score.accuracy,
    )


def run_exp003(
    matches: list[HistoricalMatch],
    *,
    config: ServeReturnConfig | None = None,
    min_train_matches: int = 1000,
    exclude_retirements: bool = True,
) -> Exp003Report:
    """EXP-003: test whether opponent-adjusted serve/return adds signal to Elo."""
    if min_train_matches <= 0:
        raise ValueError("min_train_matches must be positive")
    config = config or ServeReturnConfig()
    rows = _feature_rows(
        matches,
        config=config,
        exclude_retirements=exclude_retirements,
    )
    years = sorted({row.year for row in rows})

    predicted_rows: list[_FeatureRow] = []
    baseline_all: list[float] = []
    challenger_all: list[float] = []
    yearly: list[PeriodComparison] = []

    for test_year in years:
        train = [row for row in rows if row.year < test_year]
        test = [row for row in rows if row.year == test_year]
        if len(train) < min_train_matches or not test:
            continue
        if len({row.outcome_a for row in train}) < 2:
            continue
        baseline_probs, challenger_probs = _predict_year(train, test)
        y_true = [row.outcome_a for row in test]
        yearly.append(
            _comparison(
                year=test_year,
                y_true=y_true,
                baseline_probs=baseline_probs,
                challenger_probs=challenger_probs,
            )
        )
        predicted_rows.extend(test)
        baseline_all.extend(baseline_probs)
        challenger_all.extend(challenger_probs)

    if not predicted_rows:
        raise ValueError("no chronological predictions are available for EXP-003")

    y_all = [row.outcome_a for row in predicted_rows]
    baseline_score = _score(y_all, baseline_all)
    challenger_score = _score(y_all, challenger_all)

    history_slices: list[HistorySlice] = []
    for threshold in (0, 250, 1000):
        indices = [
            index
            for index, row in enumerate(predicted_rows)
            if row.min_prior_points >= threshold
        ]
        if not indices:
            continue
        y_true = [y_all[index] for index in indices]
        baseline_probs = [baseline_all[index] for index in indices]
        challenger_probs = [challenger_all[index] for index in indices]
        baseline_slice = _score(y_true, baseline_probs)
        challenger_slice = _score(y_true, challenger_probs)
        history_slices.append(
            HistorySlice(
                min_prior_points=threshold,
                n=len(indices),
                elo_calibrated=baseline_slice,
                elo_serve_return=challenger_slice,
                brier_improvement=baseline_slice.brier - challenger_slice.brier,
                log_loss_improvement=(
                    baseline_slice.log_loss - challenger_slice.log_loss
                ),
                accuracy_change=(
                    challenger_slice.accuracy - baseline_slice.accuracy
                ),
            )
        )

    return Exp003Report(
        experiment_id="EXP-003",
        population_n=len(predicted_rows),
        min_train_matches=min_train_matches,
        serve_return_config=config,
        elo_calibrated=baseline_score,
        elo_serve_return=challenger_score,
        brier_improvement=baseline_score.brier - challenger_score.brier,
        log_loss_improvement=baseline_score.log_loss - challenger_score.log_loss,
        accuracy_change=challenger_score.accuracy - baseline_score.accuracy,
        yearly=tuple(yearly),
        history_slices=tuple(history_slices),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run EXP-003: Elo plus opponent-adjusted serve/return"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--min-train-matches", type=int, default=1000)
    parser.add_argument(
        "--include-retirements",
        action="store_true",
        help="Include retirement matches; walkovers remain excluded",
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
    report = run_exp003(
        matches,
        min_train_matches=args.min_train_matches,
        exclude_retirements=not args.include_retirements,
    )
    print(json.dumps(asdict(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
