from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from tennis_genome.data.canonical import HistoricalMatch
from tennis_genome.data.manifest import verify_canonical_manifest
from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.evaluation.metrics import (
    accuracy,
    binary_log_loss,
    brier_score,
    expected_calibration_error,
)
from tennis_genome.features.foundational import walk_forward_foundational_features
from tennis_genome.models.core_v1_spec import (
    HISTORICAL_BENCHMARK_FEATURES,
    a_plus_b_features,
    strict_a_features,
)
from tennis_genome.models.feature_probability import FeatureProbabilityModel


@dataclass(frozen=True)
class HoldoutModelScore:
    n: int
    brier: float
    log_loss: float
    accuracy: float
    ece_10: float


@dataclass(frozen=True)
class HoldoutCandidateResult:
    name: str
    feature_names: tuple[str, ...]
    score: HoldoutModelScore
    brier_improvement_vs_benchmark: float
    log_loss_improvement_vs_benchmark: float
    accuracy_change_vs_benchmark: float


@dataclass(frozen=True)
class CoreHoldoutReport:
    experiment_id: str
    train_end_year: int
    holdout_year: int
    training_n: int
    holdout_n: int
    benchmark_name: str
    benchmark_features: tuple[str, ...]
    benchmark: HoldoutModelScore
    candidates: tuple[HoldoutCandidateResult, ...]
    sequential_state_updates: bool
    frozen_predictive_mapping: bool


def _score(outcomes: list[bool], probabilities: list[float]) -> HoldoutModelScore:
    return HoldoutModelScore(
        n=len(outcomes),
        brier=brier_score(outcomes, probabilities),
        log_loss=binary_log_loss(outcomes, probabilities),
        accuracy=accuracy(outcomes, probabilities),
        ece_10=expected_calibration_error(outcomes, probabilities, n_bins=10),
    )


def run_core_holdout(
    matches: list[HistoricalMatch],
    *,
    benchmark_name: str,
    benchmark_features: tuple[str, ...],
    candidates: dict[str, tuple[str, ...]],
    train_end_year: int = 2025,
    holdout_year: int = 2026,
    exclude_retirements: bool = True,
) -> CoreHoldoutReport:
    """Fit on history and evaluate frozen mappings on a sequential future holdout.

    Feature-state construction sees the full chronological stream so genuinely
    earlier holdout matches may update dynamic player state. The fitted mapping
    itself is trained only through ``train_end_year`` and never refit using
    holdout outcomes.
    """
    if holdout_year <= train_end_year:
        raise ValueError("holdout_year must be after train_end_year")
    if not candidates:
        raise ValueError("at least one candidate model is required")

    eligible = [
        match
        for match in matches
        if not match.outcome.walkover
        and (not exclude_retirements or not match.outcome.retirement)
        and match.pre_match.event_date.year <= holdout_year
    ]
    snapshots = walk_forward_foundational_features(
        eligible,
        exclude_retirements=False,
    )
    outcomes = {match.match_id: match.outcome.a_won for match in eligible}

    training_snapshots = [
        snapshot for snapshot in snapshots if snapshot.event_date.year <= train_end_year
    ]
    holdout_snapshots = [
        snapshot for snapshot in snapshots if snapshot.event_date.year == holdout_year
    ]
    if not training_snapshots:
        raise ValueError("no training snapshots are available")
    if not holdout_snapshots:
        raise ValueError("no holdout snapshots are available")

    training_outcomes = [outcomes[snapshot.match_id] for snapshot in training_snapshots]
    holdout_outcomes = [outcomes[snapshot.match_id] for snapshot in holdout_snapshots]

    benchmark_model = FeatureProbabilityModel(benchmark_features).fit(
        training_snapshots,
        training_outcomes,
    )
    benchmark_probabilities = benchmark_model.predict_probabilities(holdout_snapshots)
    benchmark_score = _score(holdout_outcomes, benchmark_probabilities)

    results: list[HoldoutCandidateResult] = []
    for name, feature_names in candidates.items():
        model = FeatureProbabilityModel(feature_names).fit(
            training_snapshots,
            training_outcomes,
        )
        probabilities = model.predict_probabilities(holdout_snapshots)
        score = _score(holdout_outcomes, probabilities)
        results.append(
            HoldoutCandidateResult(
                name=name,
                feature_names=feature_names,
                score=score,
                brier_improvement_vs_benchmark=benchmark_score.brier - score.brier,
                log_loss_improvement_vs_benchmark=(
                    benchmark_score.log_loss - score.log_loss
                ),
                accuracy_change_vs_benchmark=score.accuracy - benchmark_score.accuracy,
            )
        )

    return CoreHoldoutReport(
        experiment_id="CORE-V1-SEALED-HOLDOUT-001",
        train_end_year=train_end_year,
        holdout_year=holdout_year,
        training_n=len(training_snapshots),
        holdout_n=len(holdout_snapshots),
        benchmark_name=benchmark_name,
        benchmark_features=benchmark_features,
        benchmark=benchmark_score,
        candidates=tuple(results),
        sequential_state_updates=True,
        frozen_predictive_mapping=True,
    )


def report_as_dict(report: CoreHoldoutReport) -> dict[str, object]:
    return asdict(report)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the sealed partial-2026 Core v1 forward holdout"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--tour", required=True, choices=("ATP", "WTA"))
    parser.add_argument("--train-end-year", type=int, default=2025)
    parser.add_argument("--holdout-year", type=int, default=2026)
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
    tour = args.tour
    report = run_core_holdout(
        matches,
        benchmark_name="historical_elo_plus_serve_return_control",
        benchmark_features=HISTORICAL_BENCHMARK_FEATURES,
        candidates={
            "core_v1_strict_a_only": strict_a_features(tour),
            "core_v1_a_plus_b_diagnostic": a_plus_b_features(tour),
        },
        train_end_year=args.train_end_year,
        holdout_year=args.holdout_year,
        exclude_retirements=not args.include_retirements,
    )
    print(json.dumps(report_as_dict(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
