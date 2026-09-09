from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from sklearn.impute import SimpleImputer
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
from tennis_genome.features.foundational import (
    FoundationalSnapshot,
    walk_forward_foundational_features,
)

CORE_FEATURES = ("elo_logit", "serve_return_edge")
FAMILY_FEATURES: dict[str, tuple[str, ...]] = {
    "recent_form": (
        "form_result_30_diff",
        "form_result_90_diff",
        "form_point_30_diff",
        "form_point_90_diff",
    ),
    "workload_rest_proxy": (
        "event_gap_days_diff",
        "minutes_7_diff",
        "minutes_14_diff",
        "minutes_28_diff",
        "matches_14_diff",
        "matches_28_diff",
        "previous_event_minutes_diff",
    ),
    "age_career_physical": (
        "age_diff",
        "age_curve_diff",
        "young_diff",
        "veteran_diff",
        "height_diff",
    ),
    "age_fatigue_interaction": (
        "age_x_minutes_14_diff",
        "age_x_short_gap_diff",
    ),
    "head_to_head": (
        "h2h_edge",
        "h2h_weighted_edge",
    ),
    "handedness_matchup": (
        "left_hand_diff",
        "opposite_hand_serve_edge",
    ),
    "surface_tournament_context": (
        "surface_hard_elo",
        "surface_clay_elo",
        "surface_grass_elo",
        "surface_carpet_elo",
        "surface_hard_serve",
        "surface_clay_serve",
        "surface_grass_serve",
        "surface_carpet_serve",
        "slam_elo",
        "masters_elo",
        "finals_elo",
        "lower_tier_elo",
        "late_round_elo",
        "round_robin_elo",
        "best_of_five_elo",
        "qualifier_diff",
        "wildcard_diff",
        "lucky_loser_diff",
        "protected_ranking_diff",
        "seeded_diff",
        "seed_strength_diff",
    ),
}


@dataclass(frozen=True)
class ModelScore:
    n: int
    brier: float
    log_loss: float
    accuracy: float
    ece_10: float


@dataclass(frozen=True)
class FamilyResult:
    family: str
    feature_names: tuple[str, ...]
    add_one: ModelScore
    add_one_brier_improvement: float
    add_one_log_loss_improvement: float
    add_one_accuracy_change: float
    add_one_brier_winning_years: int
    add_one_log_loss_winning_years: int
    evaluated_years: int
    full_minus_family: ModelScore
    ablation_brier_contribution: float
    ablation_log_loss_contribution: float
    ablation_accuracy_contribution: float


@dataclass(frozen=True)
class ServeReturnDecomposition:
    elo_only: ModelScore
    elo_plus_serve: ModelScore
    elo_plus_return: ModelScore
    elo_plus_serve_and_return: ModelScore
    serve_brier_improvement: float
    return_brier_improvement: float
    combined_brier_improvement: float
    serve_log_loss_improvement: float
    return_log_loss_improvement: float
    combined_log_loss_improvement: float


@dataclass(frozen=True)
class FamilyLabReport:
    experiment_id: str
    population_n: int
    min_train_matches: int
    evaluated_years: int
    core_features: tuple[str, ...]
    core: ModelScore
    full: ModelScore
    full_brier_improvement: float
    full_log_loss_improvement: float
    full_accuracy_change: float
    families: tuple[FamilyResult, ...]
    serve_return_decomposition: ServeReturnDecomposition
    blocked_families: tuple[str, ...]
    timing_limitation: str


@dataclass(frozen=True)
class _Row:
    snapshot: FoundationalSnapshot
    outcome_a: bool

    @property
    def year(self) -> int:
        return self.snapshot.event_date.year


def _score(y_true: list[bool], probabilities: list[float]) -> ModelScore:
    return ModelScore(
        n=len(y_true),
        brier=brier_score(y_true, probabilities),
        log_loss=binary_log_loss(y_true, probabilities),
        accuracy=accuracy(y_true, probabilities),
        ece_10=expected_calibration_error(y_true, probabilities, n_bins=10),
    )


def _value(snapshot: FoundationalSnapshot, name: str) -> float:
    value = getattr(snapshot, name)
    return float("nan") if value is None else float(value)


def _matrix(rows: list[_Row], feature_names: tuple[str, ...]) -> list[list[float]]:
    return [[_value(row.snapshot, name) for name in feature_names] for row in rows]


def _model() -> Pipeline:
    return make_pipeline(
        SimpleImputer(
            strategy="median",
            add_indicator=True,
            keep_empty_features=True,
        ),
        StandardScaler(),
        LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000),
    )


def _fit_predict(
    train: list[_Row],
    test: list[_Row],
    feature_names: tuple[str, ...],
) -> list[float]:
    model = _model()
    y_train = [int(row.outcome_a) for row in train]
    model.fit(_matrix(train, feature_names), y_train)
    return model.predict_proba(_matrix(test, feature_names))[:, 1].tolist()


def _rows(
    matches: list[HistoricalMatch],
    *,
    exclude_retirements: bool,
) -> list[_Row]:
    snapshots = walk_forward_foundational_features(
        matches,
        exclude_retirements=exclude_retirements,
    )
    outcomes = {match.match_id: match.outcome.a_won for match in matches}
    return [
        _Row(snapshot=snapshot, outcome_a=outcomes[snapshot.match_id])
        for snapshot in snapshots
    ]


def _all_family_features() -> tuple[str, ...]:
    return tuple(name for names in FAMILY_FEATURES.values() for name in names)


def run_family_lab(
    matches: list[HistoricalMatch],
    *,
    min_train_matches: int = 1000,
    exclude_retirements: bool = True,
) -> FamilyLabReport:
    """Test every currently-supported foundational family on chronological folds."""
    if min_train_matches <= 0:
        raise ValueError("min_train_matches must be positive")
    rows = _rows(matches, exclude_retirements=exclude_retirements)
    years = sorted({row.year for row in rows})
    full_features = CORE_FEATURES + _all_family_features()

    predicted_rows: list[_Row] = []
    predictions: defaultdict[str, list[float]] = defaultdict(list)
    family_year_wins: dict[str, list[int]] = {
        family: [0, 0, 0] for family in FAMILY_FEATURES
    }

    decomposition_names = {
        "elo_only": ("elo_logit",),
        "elo_plus_serve": ("elo_logit", "serve_rating_diff"),
        "elo_plus_return": ("elo_logit", "return_rating_diff"),
        "elo_plus_serve_and_return": (
            "elo_logit",
            "serve_rating_diff",
            "return_rating_diff",
        ),
    }

    for test_year in years:
        train = [row for row in rows if row.year < test_year]
        test = [row for row in rows if row.year == test_year]
        if len(train) < min_train_matches or not test:
            continue
        if len({row.outcome_a for row in train}) < 2:
            continue

        core_probs = _fit_predict(train, test, CORE_FEATURES)
        full_probs = _fit_predict(train, test, full_features)
        predictions["core"].extend(core_probs)
        predictions["full"].extend(full_probs)
        y_year = [row.outcome_a for row in test]
        core_year = _score(y_year, core_probs)

        for family, names in FAMILY_FEATURES.items():
            add_probs = _fit_predict(train, test, CORE_FEATURES + names)
            excluded = set(names)
            without = tuple(
                feature for feature in full_features if feature not in excluded
            )
            without_probs = _fit_predict(train, test, without)
            predictions[f"add:{family}"].extend(add_probs)
            predictions[f"without:{family}"].extend(without_probs)
            add_year = _score(y_year, add_probs)
            wins = family_year_wins[family]
            wins[2] += 1
            if add_year.brier < core_year.brier:
                wins[0] += 1
            if add_year.log_loss < core_year.log_loss:
                wins[1] += 1

        for name, feature_names in decomposition_names.items():
            predictions[f"decomp:{name}"].extend(
                _fit_predict(train, test, feature_names)
            )

        predicted_rows.extend(test)

    if not predicted_rows:
        raise ValueError("no chronological predictions are available for the family lab")

    y_all = [row.outcome_a for row in predicted_rows]
    core_score = _score(y_all, predictions["core"])
    full_score = _score(y_all, predictions["full"])

    family_results: list[FamilyResult] = []
    for family, names in FAMILY_FEATURES.items():
        add_score = _score(y_all, predictions[f"add:{family}"])
        without_score = _score(y_all, predictions[f"without:{family}"])
        wins = family_year_wins[family]
        family_results.append(
            FamilyResult(
                family=family,
                feature_names=names,
                add_one=add_score,
                add_one_brier_improvement=core_score.brier - add_score.brier,
                add_one_log_loss_improvement=core_score.log_loss - add_score.log_loss,
                add_one_accuracy_change=add_score.accuracy - core_score.accuracy,
                add_one_brier_winning_years=wins[0],
                add_one_log_loss_winning_years=wins[1],
                evaluated_years=wins[2],
                full_minus_family=without_score,
                ablation_brier_contribution=without_score.brier - full_score.brier,
                ablation_log_loss_contribution=(
                    without_score.log_loss - full_score.log_loss
                ),
                ablation_accuracy_contribution=(
                    full_score.accuracy - without_score.accuracy
                ),
            )
        )

    decomp_scores = {
        name: _score(y_all, predictions[f"decomp:{name}"])
        for name in decomposition_names
    }
    elo_only = decomp_scores["elo_only"]
    decomposition = ServeReturnDecomposition(
        elo_only=elo_only,
        elo_plus_serve=decomp_scores["elo_plus_serve"],
        elo_plus_return=decomp_scores["elo_plus_return"],
        elo_plus_serve_and_return=decomp_scores["elo_plus_serve_and_return"],
        serve_brier_improvement=(
            elo_only.brier - decomp_scores["elo_plus_serve"].brier
        ),
        return_brier_improvement=(
            elo_only.brier - decomp_scores["elo_plus_return"].brier
        ),
        combined_brier_improvement=(
            elo_only.brier - decomp_scores["elo_plus_serve_and_return"].brier
        ),
        serve_log_loss_improvement=(
            elo_only.log_loss - decomp_scores["elo_plus_serve"].log_loss
        ),
        return_log_loss_improvement=(
            elo_only.log_loss - decomp_scores["elo_plus_return"].log_loss
        ),
        combined_log_loss_improvement=(
            elo_only.log_loss - decomp_scores["elo_plus_serve_and_return"].log_loss
        ),
    )

    evaluated_years = family_results[0].evaluated_years if family_results else 0
    return FamilyLabReport(
        experiment_id="FOUNDATIONAL-FAMILY-LAB-001",
        population_n=len(predicted_rows),
        min_train_matches=min_train_matches,
        evaluated_years=evaluated_years,
        core_features=CORE_FEATURES,
        core=core_score,
        full=full_score,
        full_brier_improvement=core_score.brier - full_score.brier,
        full_log_loss_improvement=core_score.log_loss - full_score.log_loss,
        full_accuracy_change=full_score.accuracy - core_score.accuracy,
        families=tuple(family_results),
        serve_return_decomposition=decomposition,
        blocked_families=(
            "weather_temperature_humidity_wind",
            "altitude_true_court_speed_ball_type",
            "injury_health",
            "travel_circadian",
            "coaching_current_events",
            "detailed_style_tracking",
        ),
        timing_limitation=(
            "Source tourney_date is event-start-era rather than trustworthy exact match time; "
            "workload/rest variables are conservative event-gap proxies and omit "
            "within-event chronology."
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the foundational metric-family add-one/ablation laboratory"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--min-train-matches", type=int, default=1000)
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
    report = run_family_lab(
        matches,
        min_train_matches=args.min_train_matches,
        exclude_retirements=not args.include_retirements,
    )
    print(json.dumps(asdict(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
