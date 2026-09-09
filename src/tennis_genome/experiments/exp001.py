from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from tennis_genome.data.canonical import HistoricalMatch
from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.evaluation.metrics import (
    accuracy,
    binary_log_loss,
    brier_score,
    expected_calibration_error,
)
from tennis_genome.evaluation.walkforward import (
    ModelPrediction,
    walk_forward_elo,
    walk_forward_ranking_logit,
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
    ranking: ModelScore
    elo: ModelScore
    brier_improvement_elo_vs_ranking: float
    log_loss_improvement_elo_vs_ranking: float
    accuracy_change_elo_vs_ranking: float


@dataclass(frozen=True)
class Exp001Report:
    experiment_id: str
    population_n: int
    ranking: ModelScore
    elo: ModelScore
    brier_improvement_elo_vs_ranking: float
    log_loss_improvement_elo_vs_ranking: float
    accuracy_change_elo_vs_ranking: float
    yearly: tuple[PeriodComparison, ...]


def _score(y_true: list[bool], probabilities: list[float]) -> ModelScore:
    return ModelScore(
        n=len(y_true),
        brier=brier_score(y_true, probabilities),
        log_loss=binary_log_loss(y_true, probabilities),
        accuracy=accuracy(y_true, probabilities),
        ece_10=expected_calibration_error(y_true, probabilities, n_bins=10),
    )


def _comparison_for_ids(
    ids: list[str],
    *,
    outcomes_by_id: dict[str, bool],
    elo_by_id: dict[str, ModelPrediction],
    ranking_by_id: dict[str, ModelPrediction],
    year: int,
) -> PeriodComparison:
    y_true = [outcomes_by_id[match_id] for match_id in ids]
    ranking_probs = [ranking_by_id[match_id].probability_a for match_id in ids]
    elo_probs = [elo_by_id[match_id].probability_a for match_id in ids]
    ranking_score = _score(y_true, ranking_probs)
    elo_score = _score(y_true, elo_probs)
    return PeriodComparison(
        year=year,
        n=len(ids),
        ranking=ranking_score,
        elo=elo_score,
        brier_improvement_elo_vs_ranking=ranking_score.brier - elo_score.brier,
        log_loss_improvement_elo_vs_ranking=ranking_score.log_loss - elo_score.log_loss,
        accuracy_change_elo_vs_ranking=elo_score.accuracy - ranking_score.accuracy,
    )


def run_exp001(
    matches: list[HistoricalMatch],
    *,
    min_train_matches: int = 500,
    exclude_retirements: bool = True,
) -> Exp001Report:
    """EXP-001: compare ranking calibration with Elo on identical future matches."""
    elo_predictions = walk_forward_elo(matches, exclude_retirements=exclude_retirements)
    ranking_predictions = walk_forward_ranking_logit(
        matches,
        min_train_matches=min_train_matches,
        exclude_retirements=exclude_retirements,
    )

    outcomes_by_id = {match.match_id: match.outcome.a_won for match in matches}
    elo_by_id = {prediction.match_id: prediction for prediction in elo_predictions}
    ranking_by_id = {prediction.match_id: prediction for prediction in ranking_predictions}
    common_ids = sorted(
        set(elo_by_id).intersection(ranking_by_id),
        key=lambda match_id: (
            ranking_by_id[match_id].event_date,
            match_id,
        ),
    )
    if not common_ids:
        raise ValueError("no common walk-forward predictions are available for EXP-001")

    y_true = [outcomes_by_id[match_id] for match_id in common_ids]
    ranking_probs = [ranking_by_id[match_id].probability_a for match_id in common_ids]
    elo_probs = [elo_by_id[match_id].probability_a for match_id in common_ids]
    ranking_score = _score(y_true, ranking_probs)
    elo_score = _score(y_true, elo_probs)

    ids_by_year: dict[int, list[str]] = {}
    for match_id in common_ids:
        year = ranking_by_id[match_id].event_date.year
        ids_by_year.setdefault(year, []).append(match_id)
    yearly = tuple(
        _comparison_for_ids(
            ids,
            outcomes_by_id=outcomes_by_id,
            elo_by_id=elo_by_id,
            ranking_by_id=ranking_by_id,
            year=year,
        )
        for year, ids in sorted(ids_by_year.items())
    )

    return Exp001Report(
        experiment_id="EXP-001",
        population_n=len(common_ids),
        ranking=ranking_score,
        elo=elo_score,
        brier_improvement_elo_vs_ranking=ranking_score.brier - elo_score.brier,
        log_loss_improvement_elo_vs_ranking=ranking_score.log_loss - elo_score.log_loss,
        accuracy_change_elo_vs_ranking=elo_score.accuracy - ranking_score.accuracy,
        yearly=yearly,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EXP-001: ranking versus Elo")
    parser.add_argument(
        "--pre-match",
        required=True,
        type=Path,
        help="Canonical pre-match Parquet table",
    )
    parser.add_argument(
        "--outcomes",
        required=True,
        type=Path,
        help="Canonical outcome Parquet table",
    )
    parser.add_argument("--min-train-matches", type=int, default=500)
    parser.add_argument(
        "--include-retirements",
        action="store_true",
        help="Include retirement matches; walkovers remain excluded",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    matches = load_canonical_parquet(
        pre_match_path=args.pre_match,
        outcome_path=args.outcomes,
    )
    report = run_exp001(
        matches,
        min_train_matches=args.min_train_matches,
        exclude_retirements=not args.include_retirements,
    )
    print(json.dumps(asdict(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
