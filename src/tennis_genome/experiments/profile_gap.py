from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from tennis_genome.data.canonical import HistoricalMatch, Tour
from tennis_genome.data.manifest import verify_canonical_manifest
from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.evaluation.metrics import (
    accuracy,
    binary_log_loss,
    brier_score,
    expected_calibration_error,
)
from tennis_genome.features.foundational import FoundationalSnapshot, walk_forward_foundational_features
from tennis_genome.models.core_v1_spec import strict_a_features
from tennis_genome.models.feature_probability import FeatureProbabilityModel
from tennis_genome.models.profile_strength import ProfileStrengthModel
from tennis_genome.profiles.features import profile_strength_feature_names
from tennis_genome.profiles.state import MatchProfilePair, walk_forward_player_profiles

_PROFILE_GAP_DEVELOPMENT_END_YEAR = 2025
_RECENT_START_YEAR = 2021
_RECENT_END_YEAR = 2025


@dataclass(frozen=True)
class ModelScore:
    n: int
    brier: float
    log_loss: float
    accuracy: float
    ece_10: float


@dataclass(frozen=True)
class ModelComparison:
    n: int
    elo: ModelScore
    profile: ModelScore
    strict_core: ModelScore
    brier_improvement_vs_elo: float
    log_loss_improvement_vs_elo: float
    accuracy_change_vs_elo: float
    brier_change_vs_core: float
    log_loss_change_vs_core: float


@dataclass(frozen=True)
class YearComparison:
    year: int
    comparison: ModelComparison
    joint_profile_win_vs_elo: bool


@dataclass(frozen=True)
class GapQuintile:
    quintile: int
    n: int
    mean_gap: float
    mean_elo_residual: float
    mean_elo_probability: float
    realized_a_win_rate: float


@dataclass(frozen=True)
class GapDiagnostic:
    n: int
    residual_slope_on_gap: float | None
    top_minus_bottom_residual: float | None
    quintiles: tuple[GapQuintile, ...]


@dataclass(frozen=True)
class DepthSlice:
    dimension: str
    threshold: int
    comparison: ModelComparison


@dataclass(frozen=True)
class DurationCoverageSlice:
    coverage: str
    comparison: ModelComparison


@dataclass(frozen=True)
class PromotionDiagnostics:
    aggregate_brier_positive: bool
    aggregate_log_loss_positive: bool
    joint_year_win_count: int
    evaluated_year_count: int
    joint_year_win_rate: float
    at_least_60_percent_joint_year_wins: bool
    recent_brier_not_worse: bool | None
    recent_log_loss_not_worse: bool | None
    gap_top_minus_bottom_positive: bool
    gap_slope_positive: bool
    recent_gap_direction_not_reversed: bool | None


@dataclass(frozen=True)
class ProfileGapReport:
    experiment_id: str
    tour: Tour
    representation: str
    feature_names: tuple[str, ...]
    min_train_matches: int
    development_end_year: int
    population_n: int
    comparison: ModelComparison
    recent_comparison: ModelComparison | None
    yearly: tuple[YearComparison, ...]
    gap: GapDiagnostic
    recent_gap: GapDiagnostic | None
    depth_slices: tuple[DepthSlice, ...]
    duration_coverage: tuple[DurationCoverageSlice, ...]
    promotion_diagnostics: PromotionDiagnostics


@dataclass(frozen=True)
class _PredictionRow:
    match_id: str
    year: int
    outcome_a: bool
    elo_probability: float
    profile_probability: float
    strict_core_probability: float
    profile_gap_match: float
    min_prior_matches: int
    min_prior_points: int
    complete_14d_duration: bool


def _score(rows: list[_PredictionRow], probability_field: str) -> ModelScore:
    if not rows:
        raise ValueError("cannot score an empty prediction set")
    y_true = [row.outcome_a for row in rows]
    probabilities = [float(getattr(row, probability_field)) for row in rows]
    return ModelScore(
        n=len(rows),
        brier=brier_score(y_true, probabilities),
        log_loss=binary_log_loss(y_true, probabilities),
        accuracy=accuracy(y_true, probabilities),
        ece_10=expected_calibration_error(y_true, probabilities, n_bins=10),
    )


def _comparison(rows: list[_PredictionRow]) -> ModelComparison:
    elo = _score(rows, "elo_probability")
    profile = _score(rows, "profile_probability")
    strict_core = _score(rows, "strict_core_probability")
    return ModelComparison(
        n=len(rows),
        elo=elo,
        profile=profile,
        strict_core=strict_core,
        brier_improvement_vs_elo=elo.brier - profile.brier,
        log_loss_improvement_vs_elo=elo.log_loss - profile.log_loss,
        accuracy_change_vs_elo=profile.accuracy - elo.accuracy,
        brier_change_vs_core=strict_core.brier - profile.brier,
        log_loss_change_vs_core=strict_core.log_loss - profile.log_loss,
    )


def _gap_quintiles(rows: list[_PredictionRow]) -> tuple[GapQuintile, ...]:
    if not rows:
        return ()
    ordered = sorted(rows, key=lambda row: (row.profile_gap_match, row.match_id))
    buckets: list[list[_PredictionRow]] = [[] for _ in range(5)]
    total = len(ordered)
    for rank, row in enumerate(ordered):
        bucket_index = min((rank * 5) // total, 4)
        buckets[bucket_index].append(row)

    result: list[GapQuintile] = []
    for index, bucket in enumerate(buckets, start=1):
        if not bucket:
            continue
        residuals = [
            (1.0 if row.outcome_a else 0.0) - row.elo_probability
            for row in bucket
        ]
        result.append(
            GapQuintile(
                quintile=index,
                n=len(bucket),
                mean_gap=sum(row.profile_gap_match for row in bucket) / len(bucket),
                mean_elo_residual=sum(residuals) / len(bucket),
                mean_elo_probability=(
                    sum(row.elo_probability for row in bucket) / len(bucket)
                ),
                realized_a_win_rate=(
                    sum(1.0 if row.outcome_a else 0.0 for row in bucket)
                    / len(bucket)
                ),
            )
        )
    return tuple(result)


def _linear_slope(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or not xs:
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((value - mean_x) ** 2 for value in xs)
    if denominator <= 0.0:
        return None
    numerator = sum(
        (x - mean_x) * (y - mean_y)
        for x, y in zip(xs, ys, strict=True)
    )
    return numerator / denominator


def _gap_diagnostic(rows: list[_PredictionRow]) -> GapDiagnostic:
    quintiles = _gap_quintiles(rows)
    gaps = [row.profile_gap_match for row in rows]
    residuals = [
        (1.0 if row.outcome_a else 0.0) - row.elo_probability
        for row in rows
    ]
    top_minus_bottom: float | None = None
    if len(quintiles) >= 2:
        top_minus_bottom = (
            quintiles[-1].mean_elo_residual - quintiles[0].mean_elo_residual
        )
    return GapDiagnostic(
        n=len(rows),
        residual_slope_on_gap=_linear_slope(gaps, residuals),
        top_minus_bottom_residual=top_minus_bottom,
        quintiles=quintiles,
    )


def _eligible_matches(
    matches: list[HistoricalMatch],
    *,
    tour: Tour,
    exclude_retirements: bool,
) -> list[HistoricalMatch]:
    if any(match.pre_match.event_date.year > _PROFILE_GAP_DEVELOPMENT_END_YEAR for match in matches):
        raise ValueError(
            "PROFILE-GAP-001 is frozen to 2000-2025 development data; "
            "post-2025 matches, including the spent 2026 holdout, are forbidden"
        )
    return [
        match
        for match in matches
        if match.pre_match.tour == tour
        and not match.outcome.walkover
        and (not exclude_retirements or not match.outcome.retirement)
    ]


def _aligned_state(
    matches: list[HistoricalMatch],
) -> tuple[
    list[MatchProfilePair],
    dict[str, FoundationalSnapshot],
    dict[str, bool],
]:
    pairs = walk_forward_player_profiles(matches, exclude_retirements=False)
    foundational = {
        snapshot.match_id: snapshot
        for snapshot in walk_forward_foundational_features(
            matches,
            exclude_retirements=False,
        )
    }
    outcomes = {match.match_id: match.outcome.a_won for match in matches}
    pairs = [pair for pair in pairs if pair.match_id in foundational]
    return pairs, foundational, outcomes


def _prediction_rows_for_year(
    *,
    tour: Tour,
    train_pairs: list[MatchProfilePair],
    test_pairs: list[MatchProfilePair],
    foundational: dict[str, FoundationalSnapshot],
    outcomes: dict[str, bool],
    include_conditional: bool,
) -> list[_PredictionRow]:
    y_train = [outcomes[pair.match_id] for pair in train_pairs]
    profile_model = ProfileStrengthModel(
        tour,
        include_conditional=include_conditional,
    ).fit(train_pairs, y_train)

    core_model = FeatureProbabilityModel(strict_a_features(tour)).fit(
        [foundational[pair.match_id] for pair in train_pairs],
        y_train,
    )
    core_probabilities = core_model.predict_probabilities(
        [foundational[pair.match_id] for pair in test_pairs]
    )
    profile_predictions = profile_model.predict_pairs(test_pairs)

    rows: list[_PredictionRow] = []
    for pair, profile_prediction, core_probability in zip(
        test_pairs,
        profile_predictions,
        core_probabilities,
        strict=True,
    ):
        min_prior_points = min(
            pair.player_a.prior_serve_points,
            pair.player_b.prior_serve_points,
            pair.player_a.prior_return_points,
            pair.player_b.prior_return_points,
        )
        rows.append(
            _PredictionRow(
                match_id=pair.match_id,
                year=pair.event_date.year,
                outcome_a=outcomes[pair.match_id],
                elo_probability=profile_prediction.elo_probability_a,
                profile_probability=profile_prediction.probability_a,
                strict_core_probability=core_probability,
                profile_gap_match=profile_prediction.profile_gap_match,
                min_prior_matches=min(
                    pair.player_a.prior_matches,
                    pair.player_b.prior_matches,
                ),
                min_prior_points=min_prior_points,
                complete_14d_duration=(
                    pair.player_a.has_complete_14d_duration
                    and pair.player_b.has_complete_14d_duration
                ),
            )
        )
    return rows


def _depth_slices(
    rows: list[_PredictionRow],
    *,
    include_point_history: bool,
) -> tuple[DepthSlice, ...]:
    result: list[DepthSlice] = []
    for threshold in (0, 10, 25, 50):
        subset = [row for row in rows if row.min_prior_matches >= threshold]
        if subset:
            result.append(
                DepthSlice(
                    dimension="min_prior_matches",
                    threshold=threshold,
                    comparison=_comparison(subset),
                )
            )
    if include_point_history:
        for threshold in (0, 250, 1000):
            subset = [row for row in rows if row.min_prior_points >= threshold]
            if subset:
                result.append(
                    DepthSlice(
                        dimension="min_prior_points",
                        threshold=threshold,
                        comparison=_comparison(subset),
                    )
                )
    return tuple(result)


def _duration_slices(rows: list[_PredictionRow]) -> tuple[DurationCoverageSlice, ...]:
    result: list[DurationCoverageSlice] = []
    for complete in (True, False):
        subset = [row for row in rows if row.complete_14d_duration is complete]
        if subset:
            result.append(
                DurationCoverageSlice(
                    coverage=("complete" if complete else "incomplete"),
                    comparison=_comparison(subset),
                )
            )
    return tuple(result)


def run_profile_gap(
    matches: list[HistoricalMatch],
    *,
    tour: Tour,
    include_conditional: bool = False,
    min_train_matches: int = 1000,
    exclude_retirements: bool = True,
) -> ProfileGapReport:
    """Run preregistered PROFILE-GAP-001 under expanding-year evaluation."""
    if min_train_matches <= 0:
        raise ValueError("min_train_matches must be positive")

    eligible = _eligible_matches(
        matches,
        tour=tour,
        exclude_retirements=exclude_retirements,
    )
    pairs, foundational, outcomes = _aligned_state(eligible)
    years = sorted({pair.event_date.year for pair in pairs})

    all_rows: list[_PredictionRow] = []
    yearly: list[YearComparison] = []
    for test_year in years:
        train_pairs = [pair for pair in pairs if pair.event_date.year < test_year]
        test_pairs = [pair for pair in pairs if pair.event_date.year == test_year]
        if len(train_pairs) < min_train_matches or not test_pairs:
            continue
        if len({outcomes[pair.match_id] for pair in train_pairs}) < 2:
            continue
        rows = _prediction_rows_for_year(
            tour=tour,
            train_pairs=train_pairs,
            test_pairs=test_pairs,
            foundational=foundational,
            outcomes=outcomes,
            include_conditional=include_conditional,
        )
        comparison = _comparison(rows)
        yearly.append(
            YearComparison(
                year=test_year,
                comparison=comparison,
                joint_profile_win_vs_elo=(
                    comparison.profile.brier < comparison.elo.brier
                    and comparison.profile.log_loss < comparison.elo.log_loss
                ),
            )
        )
        all_rows.extend(rows)

    if not all_rows:
        raise ValueError("no chronological predictions are available for PROFILE-GAP-001")

    comparison = _comparison(all_rows)
    recent_rows = [
        row
        for row in all_rows
        if _RECENT_START_YEAR <= row.year <= _RECENT_END_YEAR
    ]
    recent_comparison = _comparison(recent_rows) if recent_rows else None
    gap = _gap_diagnostic(all_rows)
    recent_gap = _gap_diagnostic(recent_rows) if recent_rows else None

    joint_wins = sum(item.joint_profile_win_vs_elo for item in yearly)
    joint_win_rate = joint_wins / len(yearly) if yearly else 0.0
    recent_brier_not_worse = (
        recent_comparison.profile.brier <= recent_comparison.elo.brier
        if recent_comparison is not None
        else None
    )
    recent_log_loss_not_worse = (
        recent_comparison.profile.log_loss <= recent_comparison.elo.log_loss
        if recent_comparison is not None
        else None
    )
    gap_top_positive = bool(
        gap.top_minus_bottom_residual is not None
        and gap.top_minus_bottom_residual > 0.0
    )
    gap_slope_positive = bool(
        gap.residual_slope_on_gap is not None
        and gap.residual_slope_on_gap > 0.0
    )
    recent_direction = (
        bool(
            recent_gap.top_minus_bottom_residual is not None
            and recent_gap.top_minus_bottom_residual >= 0.0
            and recent_gap.residual_slope_on_gap is not None
            and recent_gap.residual_slope_on_gap >= 0.0
        )
        if recent_gap is not None
        else None
    )

    feature_names = profile_strength_feature_names(
        tour,
        include_conditional=include_conditional,
    )
    include_point_history = "serve_rating" in feature_names
    return ProfileGapReport(
        experiment_id="PROFILE-GAP-001",
        tour=tour,
        representation=("conditional" if include_conditional else "strict"),
        feature_names=feature_names,
        min_train_matches=min_train_matches,
        development_end_year=_PROFILE_GAP_DEVELOPMENT_END_YEAR,
        population_n=len(all_rows),
        comparison=comparison,
        recent_comparison=recent_comparison,
        yearly=tuple(yearly),
        gap=gap,
        recent_gap=recent_gap,
        depth_slices=_depth_slices(
            all_rows,
            include_point_history=include_point_history,
        ),
        duration_coverage=_duration_slices(all_rows),
        promotion_diagnostics=PromotionDiagnostics(
            aggregate_brier_positive=comparison.brier_improvement_vs_elo > 0.0,
            aggregate_log_loss_positive=comparison.log_loss_improvement_vs_elo > 0.0,
            joint_year_win_count=joint_wins,
            evaluated_year_count=len(yearly),
            joint_year_win_rate=joint_win_rate,
            at_least_60_percent_joint_year_wins=joint_win_rate >= 0.60,
            recent_brier_not_worse=recent_brier_not_worse,
            recent_log_loss_not_worse=recent_log_loss_not_worse,
            gap_top_minus_bottom_positive=gap_top_positive,
            gap_slope_positive=gap_slope_positive,
            recent_gap_direction_not_reversed=recent_direction,
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run PROFILE-GAP-001 on the frozen 2000-2025 development history"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--tour", required=True, choices=("ATP", "WTA"))
    parser.add_argument("--min-train-matches", type=int, default=1000)
    parser.add_argument(
        "--include-conditional",
        action="store_true",
        help="Use the preregistered conditional profile representation (WTA diagnostic)",
    )
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
    report = run_profile_gap(
        matches,
        tour=args.tour,
        include_conditional=args.include_conditional,
        min_train_matches=args.min_train_matches,
        exclude_retirements=not args.include_retirements,
    )
    print(json.dumps(asdict(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
