from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from sklearn.linear_model import LogisticRegression

from tennis_genome.calibration.probability import make_calibrator
from tennis_genome.data.canonical import HistoricalMatch
from tennis_genome.data.manifest import verify_canonical_manifest
from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.evaluation.metrics import (
    CalibrationBin,
    accuracy,
    binary_log_loss,
    brier_score,
    calibration_bins,
    expected_calibration_error,
)
from tennis_genome.features.foundational import (
    FoundationalSnapshot,
    walk_forward_foundational_features,
)
from tennis_genome.models.core_v1_spec import (
    ELO_FEATURES,
    Tour,
    a_plus_b_features,
    strict_a_features,
)
from tennis_genome.models.feature_probability import FeatureProbabilityModel

CALIBRATOR_NAMES = ("identity", "platt", "beta", "isotonic")
COVERAGE_LEVELS = (1.0, 0.75, 0.50, 0.25, 0.10, 0.05)
RECENT_YEARS = (2021, 2022, 2023, 2024, 2025)


@dataclass(frozen=True)
class OOFPrediction:
    match_id: str
    year: int
    outcome_a: bool
    elo_probability: float
    strict_probability: float
    a_plus_b_probability: float

    @property
    def disagreement(self) -> float:
        values = (
            self.elo_probability,
            self.strict_probability,
            self.a_plus_b_probability,
        )
        return max(values) - min(values)


@dataclass(frozen=True)
class ScoredProbabilitySet:
    n: int
    brier: float
    log_loss: float
    accuracy: float
    ece_10: float
    mean_probability: float
    observed_rate: float
    calibration_intercept: float | None
    calibration_slope: float | None
    reliability: tuple[CalibrationBin, ...]


@dataclass(frozen=True)
class CalibrationYearResult:
    year: int
    n: int
    calibration_train_n: int
    score: ScoredProbabilitySet


@dataclass(frozen=True)
class CalibrationMethodResult:
    name: str
    score: ScoredProbabilitySet
    recent_score: ScoredProbabilitySet | None
    yearly: tuple[CalibrationYearResult, ...]


@dataclass(frozen=True)
class CoverageResult:
    requested_coverage: float
    realized_coverage: float
    n: int
    score: ScoredProbabilitySet
    mean_favorite_probability: float
    realized_favorite_win_rate: float
    minimum_confidence: float


@dataclass(frozen=True)
class SelectiveMethodResult:
    calibrator: str
    coverage: tuple[CoverageResult, ...]


@dataclass(frozen=True)
class DisagreementBucket:
    quintile: int
    n: int
    mean_disagreement: float
    mean_probability_confidence: float
    strict_core_score: ScoredProbabilitySet


@dataclass(frozen=True)
class DisagreementCell:
    confidence_quintile: int
    disagreement_quintile: int
    n: int
    strict_core_score: ScoredProbabilitySet


@dataclass(frozen=True)
class DisagreementReport:
    elo_score: ScoredProbabilitySet
    strict_core_score: ScoredProbabilitySet
    a_plus_b_score: ScoredProbabilitySet
    by_disagreement_quintile: tuple[DisagreementBucket, ...]
    confidence_x_disagreement: tuple[DisagreementCell, ...]


@dataclass(frozen=True)
class CalibrationSelectiveReport:
    experiment_id: str
    tour: Tour
    min_train_matches: int
    min_calibration_predictions: int
    base_oof_n: int
    calibration_population_n: int
    base_oof_years: tuple[int, ...]
    calibration_years: tuple[int, ...]
    calibrators: tuple[CalibrationMethodResult, ...]
    selective_prediction: tuple[SelectiveMethodResult, ...]
    disagreement: DisagreementReport
    spent_holdout_note: str


@dataclass(frozen=True)
class _SnapshotRow:
    snapshot: FoundationalSnapshot
    outcome_a: bool

    @property
    def year(self) -> int:
        return self.snapshot.event_date.year


@dataclass(frozen=True)
class _CalibratedRow:
    oof: OOFPrediction
    probabilities: dict[str, float]


def _rows(
    matches: list[HistoricalMatch],
    *,
    exclude_retirements: bool,
) -> list[_SnapshotRow]:
    eligible = [
        match
        for match in matches
        if not match.outcome.walkover
        and (not exclude_retirements or not match.outcome.retirement)
        and match.pre_match.event_date.year <= 2025
    ]
    snapshots = walk_forward_foundational_features(
        eligible,
        exclude_retirements=False,
    )
    outcomes = {match.match_id: match.outcome.a_won for match in eligible}
    return [
        _SnapshotRow(snapshot=snapshot, outcome_a=outcomes[snapshot.match_id])
        for snapshot in snapshots
    ]


def _fit_predict(
    train: list[_SnapshotRow],
    test: list[_SnapshotRow],
    feature_names: tuple[str, ...],
) -> list[float]:
    model = FeatureProbabilityModel(feature_names).fit(
        [row.snapshot for row in train],
        [row.outcome_a for row in train],
    )
    return model.predict_probabilities([row.snapshot for row in test])


def generate_oof_predictions(
    matches: list[HistoricalMatch],
    *,
    tour: Tour,
    min_train_matches: int = 1000,
    exclude_retirements: bool = True,
) -> list[OOFPrediction]:
    """Generate three probability views using only earlier-year training rows."""
    if min_train_matches <= 0:
        raise ValueError("min_train_matches must be positive")

    rows = _rows(matches, exclude_retirements=exclude_retirements)
    years = sorted({row.year for row in rows})
    strict_features = strict_a_features(tour)
    diagnostic_features = a_plus_b_features(tour)
    predictions: list[OOFPrediction] = []

    for test_year in years:
        train = [row for row in rows if row.year < test_year]
        test = [row for row in rows if row.year == test_year]
        if len(train) < min_train_matches or not test:
            continue
        if len({row.outcome_a for row in train}) < 2:
            continue

        elo_probabilities = _fit_predict(train, test, ELO_FEATURES)
        strict_probabilities = _fit_predict(train, test, strict_features)
        diagnostic_probabilities = _fit_predict(
            train,
            test,
            diagnostic_features,
        )
        for row, p_elo, p_strict, p_ab in zip(
            test,
            elo_probabilities,
            strict_probabilities,
            diagnostic_probabilities,
            strict=True,
        ):
            predictions.append(
                OOFPrediction(
                    match_id=row.snapshot.match_id,
                    year=test_year,
                    outcome_a=row.outcome_a,
                    elo_probability=p_elo,
                    strict_probability=p_strict,
                    a_plus_b_probability=p_ab,
                )
            )

    if not predictions:
        raise ValueError("no chronological OOF predictions are available")
    return predictions


def _calibration_line(
    outcomes: list[bool],
    probabilities: list[float],
) -> tuple[float | None, float | None]:
    if len(set(outcomes)) < 2:
        return None, None
    epsilon = 1e-6
    logits = [
        [math.log(p / (1.0 - p))]
        for p in (min(max(float(value), epsilon), 1.0 - epsilon) for value in probabilities)
    ]
    model = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
    model.fit(logits, [int(value) for value in outcomes])
    return float(model.intercept_[0]), float(model.coef_[0][0])


def _score(
    outcomes: list[bool],
    probabilities: list[float],
) -> ScoredProbabilitySet:
    if len(outcomes) != len(probabilities) or not outcomes:
        raise ValueError("score inputs must have equal non-zero length")
    intercept, slope = _calibration_line(outcomes, probabilities)
    return ScoredProbabilitySet(
        n=len(outcomes),
        brier=brier_score(outcomes, probabilities),
        log_loss=binary_log_loss(outcomes, probabilities),
        accuracy=accuracy(outcomes, probabilities),
        ece_10=expected_calibration_error(outcomes, probabilities, n_bins=10),
        mean_probability=sum(probabilities) / len(probabilities),
        observed_rate=sum(outcomes) / len(outcomes),
        calibration_intercept=intercept,
        calibration_slope=slope,
        reliability=tuple(calibration_bins(outcomes, probabilities, n_bins=10)),
    )


def calibrate_oof_predictions(
    oof: list[OOFPrediction],
    *,
    min_calibration_predictions: int = 1000,
) -> tuple[list[_CalibratedRow], dict[str, tuple[CalibrationYearResult, ...]]]:
    """Calibrate each year using only earlier out-of-sample predictions."""
    if min_calibration_predictions <= 0:
        raise ValueError("min_calibration_predictions must be positive")

    calibrated_rows: list[_CalibratedRow] = []
    yearly_results: dict[str, list[CalibrationYearResult]] = {name: [] for name in CALIBRATOR_NAMES}
    years = sorted({row.year for row in oof})

    for year in years:
        prior = [row for row in oof if row.year < year]
        current = [row for row in oof if row.year == year]
        if len(prior) < min_calibration_predictions or not current:
            continue
        prior_outcomes = [row.outcome_a for row in prior]
        if len(set(prior_outcomes)) < 2:
            continue

        prior_probabilities = [row.strict_probability for row in prior]
        current_probabilities = [row.strict_probability for row in current]
        method_probabilities: dict[str, list[float]] = {}

        for name in CALIBRATOR_NAMES:
            calibrator = make_calibrator(name).fit(
                prior_probabilities,
                prior_outcomes,
            )
            probabilities = calibrator.predict(current_probabilities)
            method_probabilities[name] = probabilities
            yearly_results[name].append(
                CalibrationYearResult(
                    year=year,
                    n=len(current),
                    calibration_train_n=len(prior),
                    score=_score(
                        [row.outcome_a for row in current],
                        probabilities,
                    ),
                )
            )

        for index, row in enumerate(current):
            calibrated_rows.append(
                _CalibratedRow(
                    oof=row,
                    probabilities={
                        name: method_probabilities[name][index] for name in CALIBRATOR_NAMES
                    },
                )
            )

    if not calibrated_rows:
        raise ValueError("no nested calibration years are available")
    return calibrated_rows, {name: tuple(results) for name, results in yearly_results.items()}


def _method_result(
    name: str,
    rows: list[_CalibratedRow],
    yearly: tuple[CalibrationYearResult, ...],
) -> CalibrationMethodResult:
    outcomes = [row.oof.outcome_a for row in rows]
    probabilities = [row.probabilities[name] for row in rows]
    recent = [row for row in rows if row.oof.year in RECENT_YEARS]
    recent_score = None
    if recent:
        recent_score = _score(
            [row.oof.outcome_a for row in recent],
            [row.probabilities[name] for row in recent],
        )
    return CalibrationMethodResult(
        name=name,
        score=_score(outcomes, probabilities),
        recent_score=recent_score,
        yearly=yearly,
    )


def _favorite_summary(
    rows: list[_CalibratedRow],
    *,
    calibrator: str,
) -> tuple[float, float]:
    favorite_probabilities: list[float] = []
    favorite_wins: list[bool] = []
    for row in rows:
        probability = row.probabilities[calibrator]
        favorite_probabilities.append(max(probability, 1.0 - probability))
        favorite_wins.append(row.oof.outcome_a if probability >= 0.5 else not row.oof.outcome_a)
    return (
        sum(favorite_probabilities) / len(favorite_probabilities),
        sum(favorite_wins) / len(favorite_wins),
    )


def selective_curve(
    rows: list[_CalibratedRow],
    *,
    calibrator: str,
) -> SelectiveMethodResult:
    ordered = sorted(
        rows,
        key=lambda row: (
            -abs(row.probabilities[calibrator] - 0.5),
            row.oof.year,
            row.oof.match_id,
        ),
    )
    total = len(ordered)
    results: list[CoverageResult] = []
    for coverage in COVERAGE_LEVELS:
        keep = max(1, min(total, math.ceil(total * coverage)))
        selected = ordered[:keep]
        outcomes = [row.oof.outcome_a for row in selected]
        probabilities = [row.probabilities[calibrator] for row in selected]
        mean_favorite, realized_favorite = _favorite_summary(
            selected,
            calibrator=calibrator,
        )
        results.append(
            CoverageResult(
                requested_coverage=coverage,
                realized_coverage=keep / total,
                n=keep,
                score=_score(outcomes, probabilities),
                mean_favorite_probability=mean_favorite,
                realized_favorite_win_rate=realized_favorite,
                minimum_confidence=min(
                    abs(row.probabilities[calibrator] - 0.5) for row in selected
                ),
            )
        )
    return SelectiveMethodResult(
        calibrator=calibrator,
        coverage=tuple(results),
    )


def _rank_quintiles(values: list[float]) -> list[int]:
    if not values:
        return []
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    buckets = [0] * len(values)
    for rank, index in enumerate(order):
        buckets[index] = min(5, (rank * 5) // len(values) + 1)
    return buckets


def disagreement_report(rows: list[_CalibratedRow]) -> DisagreementReport:
    outcomes = [row.oof.outcome_a for row in rows]
    elo = [row.oof.elo_probability for row in rows]
    strict = [row.oof.strict_probability for row in rows]
    diagnostic = [row.oof.a_plus_b_probability for row in rows]
    disagreements = [row.oof.disagreement for row in rows]
    confidences = [abs(row.oof.strict_probability - 0.5) for row in rows]
    disagreement_buckets = _rank_quintiles(disagreements)
    confidence_buckets = _rank_quintiles(confidences)

    bucket_results: list[DisagreementBucket] = []
    for quintile in range(1, 6):
        indices = [index for index, bucket in enumerate(disagreement_buckets) if bucket == quintile]
        if not indices:
            continue
        bucket_results.append(
            DisagreementBucket(
                quintile=quintile,
                n=len(indices),
                mean_disagreement=sum(disagreements[i] for i in indices) / len(indices),
                mean_probability_confidence=sum(confidences[i] for i in indices) / len(indices),
                strict_core_score=_score(
                    [outcomes[i] for i in indices],
                    [strict[i] for i in indices],
                ),
            )
        )

    cells: list[DisagreementCell] = []
    grouped: defaultdict[tuple[int, int], list[int]] = defaultdict(list)
    for index, (confidence_bucket, disagreement_bucket) in enumerate(
        zip(confidence_buckets, disagreement_buckets, strict=True)
    ):
        grouped[(confidence_bucket, disagreement_bucket)].append(index)
    for (confidence_bucket, disagreement_bucket), indices in sorted(grouped.items()):
        cells.append(
            DisagreementCell(
                confidence_quintile=confidence_bucket,
                disagreement_quintile=disagreement_bucket,
                n=len(indices),
                strict_core_score=_score(
                    [outcomes[i] for i in indices],
                    [strict[i] for i in indices],
                ),
            )
        )

    return DisagreementReport(
        elo_score=_score(outcomes, elo),
        strict_core_score=_score(outcomes, strict),
        a_plus_b_score=_score(outcomes, diagnostic),
        by_disagreement_quintile=tuple(bucket_results),
        confidence_x_disagreement=tuple(cells),
    )


def run_calibration_selective_lab(
    matches: list[HistoricalMatch],
    *,
    tour: Tour,
    min_train_matches: int = 1000,
    min_calibration_predictions: int = 1000,
    exclude_retirements: bool = True,
) -> CalibrationSelectiveReport:
    oof = generate_oof_predictions(
        matches,
        tour=tour,
        min_train_matches=min_train_matches,
        exclude_retirements=exclude_retirements,
    )
    calibrated, yearly = calibrate_oof_predictions(
        oof,
        min_calibration_predictions=min_calibration_predictions,
    )
    methods = tuple(_method_result(name, calibrated, yearly[name]) for name in CALIBRATOR_NAMES)
    selective = tuple(selective_curve(calibrated, calibrator=name) for name in CALIBRATOR_NAMES)
    return CalibrationSelectiveReport(
        experiment_id="CAL-SEL-001",
        tour=tour,
        min_train_matches=min_train_matches,
        min_calibration_predictions=min_calibration_predictions,
        base_oof_n=len(oof),
        calibration_population_n=len(calibrated),
        base_oof_years=tuple(sorted({row.year for row in oof})),
        calibration_years=tuple(sorted({row.oof.year for row in calibrated})),
        calibrators=methods,
        selective_prediction=selective,
        disagreement=disagreement_report(calibrated),
        spent_holdout_note=(
            "The partial-2026 Core v1 holdout has already been inspected and is not "
            "used anywhere in CAL-SEL-001. Any promoted post-Core-v1 change still "
            "requires genuinely later forward confirmation."
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run nested chronological calibration and selective prediction"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--tour", required=True, choices=("ATP", "WTA"))
    parser.add_argument("--min-train-matches", type=int, default=1000)
    parser.add_argument("--min-calibration-predictions", type=int, default=1000)
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
    report = run_calibration_selective_lab(
        matches,
        tour=args.tour,
        min_train_matches=args.min_train_matches,
        min_calibration_predictions=args.min_calibration_predictions,
        exclude_retirements=not args.include_retirements,
    )
    print(json.dumps(asdict(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
