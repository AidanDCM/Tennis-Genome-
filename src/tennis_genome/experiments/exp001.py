from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

from tennis_genome.data.canonical import HistoricalMatch, Tour
from tennis_genome.data.sackmann import load_sackmann_csv
from tennis_genome.evaluation.metrics import accuracy, binary_log_loss, brier_score
from tennis_genome.evaluation.walkforward import walk_forward_elo, walk_forward_ranking_logit


@dataclass(frozen=True)
class ModelScore:
    n: int
    brier: float
    log_loss: float
    accuracy: float


@dataclass(frozen=True)
class Exp001Report:
    experiment_id: str
    population_n: int
    ranking: ModelScore
    elo: ModelScore
    brier_improvement_elo_vs_ranking: float
    log_loss_improvement_elo_vs_ranking: float
    accuracy_change_elo_vs_ranking: float


def _score(y_true: list[bool], probabilities: list[float]) -> ModelScore:
    return ModelScore(
        n=len(y_true),
        brier=brier_score(y_true, probabilities),
        log_loss=binary_log_loss(y_true, probabilities),
        accuracy=accuracy(y_true, probabilities),
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

    elo_by_id = {prediction.match_id: prediction for prediction in elo_predictions}
    ranking_by_id = {prediction.match_id: prediction for prediction in ranking_predictions}
    common_ids = sorted(
        set(elo_by_id).intersection(ranking_by_id),
        key=lambda match_id: ranking_by_id[match_id].event_date,
    )
    if not common_ids:
        raise ValueError("no common walk-forward predictions are available for EXP-001")

    y_true = [ranking_by_id[match_id].actual_a_won for match_id in common_ids]
    ranking_probs = [ranking_by_id[match_id].probability_a for match_id in common_ids]
    elo_probs = [elo_by_id[match_id].probability_a for match_id in common_ids]

    ranking_score = _score(y_true, ranking_probs)
    elo_score = _score(y_true, elo_probs)
    return Exp001Report(
        experiment_id="EXP-001",
        population_n=len(common_ids),
        ranking=ranking_score,
        elo=elo_score,
        brier_improvement_elo_vs_ranking=ranking_score.brier - elo_score.brier,
        log_loss_improvement_elo_vs_ranking=ranking_score.log_loss - elo_score.log_loss,
        accuracy_change_elo_vs_ranking=elo_score.accuracy - ranking_score.accuracy,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EXP-001: ranking versus Elo")
    parser.add_argument("--input", required=True, type=Path, help="Local historical match CSV")
    parser.add_argument("--tour", required=True, choices=("ATP", "WTA"))
    parser.add_argument("--min-train-matches", type=int, default=500)
    parser.add_argument(
        "--include-retirements",
        action="store_true",
        help="Include retirement matches; walkovers remain excluded",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    tour = cast(Tour, args.tour)
    matches = load_sackmann_csv(args.input, tour=tour)
    report = run_exp001(
        matches,
        min_train_matches=args.min_train_matches,
        exclude_retirements=not args.include_retirements,
    )
    print(json.dumps(asdict(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
