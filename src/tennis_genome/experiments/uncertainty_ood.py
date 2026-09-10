from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from sklearn.linear_model import LinearRegression, Ridge
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
from tennis_genome.experiments.calibration_selective import (
    OOFPrediction,
    generate_oof_predictions,
)
from tennis_genome.experiments.genome_neighborhood import _eligible_matches
from tennis_genome.features.foundational import (
    FoundationalSnapshot,
    walk_forward_foundational_features,
)
from tennis_genome.features.genome import GENOME_VERSION, GenomeVector, build_genome_vector
from tennis_genome.neighbors.historical import HistoricalGenomeIndex, ResidualRecord
from tennis_genome.profiles.state import MatchProfilePair, walk_forward_player_profiles

_DEVELOPMENT_END_YEAR = 2025
_RECENT_START_YEAR = 2021
_RECENT_END_YEAR = 2025
_PRIMARY_K = 100
_COVERAGE_LEVELS = (1.0, 0.75, 0.50, 0.25, 0.10, 0.05)
_PRIMARY_OPERATIONAL_COVERAGES = (0.75, 0.50, 0.25)


@dataclass(frozen=True)
class Score:
    n: int
    brier: float
    log_loss: float
    accuracy: float
    ece_10: float


@dataclass(frozen=True)
class SignalQuintile:
    quintile: int
    n: int
    mean_signal: float
    brier_contribution: float
    log_loss_contribution: float
    mean_absolute_residual: float
    accuracy: float


@dataclass(frozen=True)
class SignalDiagnostic:
    n: int
    brier_slope: float | None
    log_loss_slope: float | None
    absolute_residual_slope: float | None
    q5_minus_q1_brier: float | None
    q5_minus_q1_log_loss: float | None
    q5_minus_q1_absolute_residual: float | None
    quintiles: tuple[SignalQuintile, ...]


@dataclass(frozen=True)
class SelectiveCoverage:
    requested_coverage: float
    n: int
    realized_coverage: float
    confidence_baseline: Score
    uncertainty_model: Score
    brier_improvement: float
    log_loss_improvement: float
    accuracy_change: float


@dataclass(frozen=True)
class SelectiveComparison:
    n: int
    coverage: tuple[SelectiveCoverage, ...]


@dataclass(frozen=True)
class PromotionDiagnostics:
    conditioned_density_pass: bool
    disagreement_pass: bool
    missingness_pass: bool
    history_depth_pass: bool
    point_depth_pass: bool | None
    operational_brier_win_count: int
    operational_log_loss_win_count: int
    operational_coverage_count: int
    mean_operational_brier_improvement: float
    mean_operational_log_loss_improvement: float
    recent_mean_operational_brier_improvement: float | None
    recent_mean_operational_log_loss_improvement: float | None
    monotone_uncertainty_brier_through_25pct: bool
    combined_uncertainty_pass: bool


@dataclass(frozen=True)
class PredictionLedgerRow:
    match_id: str
    year: int
    outcome_a: bool
    core_probability_a: float
    predicted_brier_risk: float
    core_confidence: float
    conditioned_unfamiliarity: float
    disagreement: float
    alignment_missing_fraction: float
    min_prior_matches: int
    min_prior_point_exposure: int | None
    raw_mean_distance_100: float
    historical_pool_size: int


@dataclass(frozen=True)
class UncertaintyOODReport:
    experiment_id: str
    tour: Tour
    development_end_year: int
    alignment_representation: str
    primary_k: int
    min_core_train_matches: int
    min_neighbor_pool: int
    min_condition_train_rows: int
    min_risk_train_rows: int
    distance_population_n: int
    conditioned_population_n: int
    risk_population_n: int
    conditioned_unfamiliarity: SignalDiagnostic
    recent_conditioned_unfamiliarity: SignalDiagnostic | None
    disagreement: SignalDiagnostic
    recent_disagreement: SignalDiagnostic | None
    missingness: SignalDiagnostic
    recent_missingness: SignalDiagnostic | None
    history_depth: SignalDiagnostic
    recent_history_depth: SignalDiagnostic | None
    point_depth: SignalDiagnostic | None
    recent_point_depth: SignalDiagnostic | None
    selective: SelectiveComparison
    recent_selective: SelectiveComparison | None
    promotion_diagnostics: PromotionDiagnostics
    predictions: tuple[PredictionLedgerRow, ...]


@dataclass(frozen=True)
class _BaseRow:
    match_id: str
    year: int
    outcome_a: bool
    core_probability_a: float
    disagreement: float
    alignment_vector: GenomeVector
    min_prior_matches: int
    min_prior_point_exposure: int | None

    @property
    def core_confidence(self) -> float:
        return abs(self.core_probability_a - 0.5)


@dataclass(frozen=True)
class _DistanceRow:
    base: _BaseRow
    raw_mean_distance_100: float
    historical_pool_size: int
    conditioned_unfamiliarity: float | None = None


@dataclass(frozen=True)
class _RiskRow:
    distance: _DistanceRow
    predicted_brier_risk: float


def _project_core(genome: GenomeVector) -> GenomeVector:
    indexes = [
        index
        for index, name in enumerate(genome.feature_names)
        if name.startswith("core::")
    ]
    if not indexes:
        raise ValueError("Genome has no strict-Core features")
    return GenomeVector(
        match_id=genome.match_id,
        event_date=genome.event_date,
        tour=genome.tour,
        player_a_id=genome.player_a_id,
        player_b_id=genome.player_b_id,
        orientation_sign=genome.orientation_sign,
        feature_names=tuple(genome.feature_names[index] for index in indexes),
        values=tuple(genome.values[index] for index in indexes),
        feature_version=f"{genome.feature_version}:core-only",
    )


def _alignment_vector(genome: GenomeVector, *, tour: Tour) -> GenomeVector:
    if genome.feature_version != GENOME_VERSION:
        raise RuntimeError(
            "UNCERTAINTY-OOD-001 requires the merged Genome v1 representation"
        )
    if tour == "ATP":
        return genome
    if tour == "WTA":
        return _project_core(genome)
    raise ValueError(f"unsupported tour: {tour!r}")


def _aligned_base_rows(
    matches: list[HistoricalMatch],
    *,
    tour: Tour,
    min_core_train_matches: int,
) -> list[_BaseRow]:
    eligible = _eligible_matches(matches, tour=tour, exclude_retirements=True)
    if any(
        match.pre_match.event_date.year > _DEVELOPMENT_END_YEAR
        for match in eligible
    ):
        raise ValueError("post-2025 data are forbidden in UNCERTAINTY-OOD-001")

    oof = generate_oof_predictions(
        eligible,
        tour=tour,
        min_train_matches=min_core_train_matches,
        exclude_retirements=False,
    )
    oof_by_id: dict[str, OOFPrediction] = {row.match_id: row for row in oof}
    foundational: dict[str, FoundationalSnapshot] = {
        snapshot.match_id: snapshot
        for snapshot in walk_forward_foundational_features(
            eligible,
            exclude_retirements=False,
        )
    }
    profiles: dict[str, MatchProfilePair] = {
        pair.match_id: pair
        for pair in walk_forward_player_profiles(
            eligible,
            exclude_retirements=False,
        )
    }

    rows: list[_BaseRow] = []
    for match_id, prediction in oof_by_id.items():
        if match_id not in foundational or match_id not in profiles:
            raise RuntimeError("OOF prediction is missing aligned pre-match state")
        pair = profiles[match_id]
        genome = build_genome_vector(pair, foundational[match_id])
        selected = _alignment_vector(genome, tour=tour)
        min_prior_matches = min(
            pair.player_a.prior_matches,
            pair.player_b.prior_matches,
        )
        min_point: int | None = None
        if tour == "ATP":
            min_point = min(
                pair.player_a.prior_serve_points,
                pair.player_a.prior_return_points,
                pair.player_b.prior_serve_points,
                pair.player_b.prior_return_points,
            )
        rows.append(
            _BaseRow(
                match_id=match_id,
                year=prediction.year,
                outcome_a=prediction.outcome_a,
                core_probability_a=prediction.strict_probability,
                disagreement=prediction.disagreement,
                alignment_vector=selected,
                min_prior_matches=min_prior_matches,
                min_prior_point_exposure=min_point,
            )
        )
    return sorted(rows, key=lambda row: (row.year, row.match_id))


def _build_distance_rows(
    rows: list[_BaseRow],
    *,
    min_neighbor_pool: int,
) -> list[_DistanceRow]:
    result: list[_DistanceRow] = []
    years = sorted({row.year for row in rows})
    for test_year in years:
        historical = [row for row in rows if row.year < test_year]
        targets = [row for row in rows if row.year == test_year]
        if len(historical) < min_neighbor_pool or not targets:
            continue
        index = HistoricalGenomeIndex(
            [
                ResidualRecord(
                    genome=row.alignment_vector,
                    residual_favorite=0.0,
                )
                for row in historical
            ]
        )
        candidates = index.query_candidates(
            [row.alignment_vector for row in targets],
            candidate_limit=_PRIMARY_K,
        )
        for row, candidate_set in zip(targets, candidates, strict=True):
            summary = index.summarize(
                row.alignment_vector,
                candidate_set,
                k=_PRIMARY_K,
            )
            if summary is None:
                raise RuntimeError(
                    "registered k=100 unavailable despite historical pool gate"
                )
            result.append(
                _DistanceRow(
                    base=row,
                    raw_mean_distance_100=summary.mean_distance,
                    historical_pool_size=len(historical),
                )
            )
    return result


def _conditioning_x(row: _DistanceRow) -> list[float]:
    confidence = row.base.core_confidence
    return [
        confidence,
        confidence * confidence,
        math.log(max(row.historical_pool_size, 1)),
    ]


def _condition_distances(
    rows: list[_DistanceRow],
    *,
    min_condition_train_rows: int,
) -> list[_DistanceRow]:
    result: list[_DistanceRow] = []
    years = sorted({row.base.year for row in rows})
    for test_year in years:
        prior = [row for row in rows if row.base.year < test_year]
        current = [row for row in rows if row.base.year == test_year]
        if len(prior) < min_condition_train_rows or not current:
            continue
        model = LinearRegression()
        x_prior = [_conditioning_x(row) for row in prior]
        y_prior = [
            math.log(max(row.raw_mean_distance_100, 1e-12))
            for row in prior
        ]
        model.fit(x_prior, y_prior)
        fitted_prior = model.predict(x_prior).tolist()
        residuals = [
            observed - predicted
            for observed, predicted in zip(y_prior, fitted_prior, strict=True)
        ]
        mean_residual = sum(residuals) / len(residuals)
        variance = (
            sum((value - mean_residual) ** 2 for value in residuals)
            / len(residuals)
        )
        residual_sd = math.sqrt(variance)
        if not math.isfinite(residual_sd) or residual_sd <= 0.0:
            continue
        predictions = model.predict(
            [_conditioning_x(row) for row in current]
        ).tolist()
        for row, expected in zip(current, predictions, strict=True):
            observed = math.log(max(row.raw_mean_distance_100, 1e-12))
            result.append(
                replace(
                    row,
                    conditioned_unfamiliarity=(observed - expected) / residual_sd,
                )
            )
    return result


def _risk_features(row: _DistanceRow, *, tour: Tour) -> list[float]:
    if row.conditioned_unfamiliarity is None:
        raise ValueError("risk features require conditioned unfamiliarity")
    values = [
        row.base.core_confidence,
        float(row.conditioned_unfamiliarity),
        row.base.disagreement,
        row.base.alignment_vector.missing_fraction,
        math.log1p(row.base.min_prior_matches),
    ]
    if tour == "ATP":
        if row.base.min_prior_point_exposure is None:
            raise RuntimeError("ATP risk row is missing point-history depth")
        values.append(math.log1p(row.base.min_prior_point_exposure))
    return values


def _brier_contribution(row: _DistanceRow) -> float:
    y = 1.0 if row.base.outcome_a else 0.0
    return (row.base.core_probability_a - y) ** 2


def _log_loss_contribution(row: _DistanceRow) -> float:
    p = min(max(row.base.core_probability_a, 1e-15), 1.0 - 1e-15)
    return -math.log(p if row.base.outcome_a else 1.0 - p)


def _build_risk_rows(
    rows: list[_DistanceRow],
    *,
    tour: Tour,
    min_risk_train_rows: int,
) -> list[_RiskRow]:
    conditioned = [
        row for row in rows if row.conditioned_unfamiliarity is not None
    ]
    result: list[_RiskRow] = []
    years = sorted({row.base.year for row in conditioned})
    for test_year in years:
        prior = [row for row in conditioned if row.base.year < test_year]
        current = [row for row in conditioned if row.base.year == test_year]
        if len(prior) < min_risk_train_rows or not current:
            continue
        model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
        model.fit(
            [_risk_features(row, tour=tour) for row in prior],
            [_brier_contribution(row) for row in prior],
        )
        predictions = model.predict(
            [_risk_features(row, tour=tour) for row in current]
        ).tolist()
        for row, predicted in zip(current, predictions, strict=True):
            result.append(
                _RiskRow(
                    distance=row,
                    predicted_brier_risk=float(predicted),
                )
            )
    return result


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


def _signal_value(row: _DistanceRow, field: str) -> float:
    if field == "conditioned_unfamiliarity":
        if row.conditioned_unfamiliarity is None:
            raise ValueError("conditioned signal missing")
        return float(row.conditioned_unfamiliarity)
    if field == "disagreement":
        return row.base.disagreement
    if field == "missingness":
        return row.base.alignment_vector.missing_fraction
    if field == "history_depth":
        return math.log1p(row.base.min_prior_matches)
    if field == "point_depth":
        if row.base.min_prior_point_exposure is None:
            raise ValueError("point depth unavailable")
        return math.log1p(row.base.min_prior_point_exposure)
    raise ValueError(f"unknown uncertainty signal: {field}")


def _signal_diagnostic(
    rows: list[_DistanceRow],
    *,
    field: str,
) -> SignalDiagnostic:
    available = [
        row
        for row in rows
        if row.conditioned_unfamiliarity is not None
        and (
            field != "point_depth"
            or row.base.min_prior_point_exposure is not None
        )
    ]
    if not available:
        return SignalDiagnostic(
            0,
            None,
            None,
            None,
            None,
            None,
            None,
            (),
        )
    ordered = sorted(
        available,
        key=lambda row: (_signal_value(row, field), row.base.match_id),
    )
    buckets: list[list[_DistanceRow]] = [[] for _ in range(5)]
    for rank, row in enumerate(ordered):
        buckets[min((rank * 5) // len(ordered), 4)].append(row)

    quintiles: list[SignalQuintile] = []
    for index, bucket in enumerate(buckets, start=1):
        if not bucket:
            continue
        briers = [_brier_contribution(row) for row in bucket]
        log_losses = [_log_loss_contribution(row) for row in bucket]
        abs_residuals = [
            abs(
                (1.0 if row.base.outcome_a else 0.0)
                - row.base.core_probability_a
            )
            for row in bucket
        ]
        correct = [
            (row.base.core_probability_a >= 0.5) == row.base.outcome_a
            for row in bucket
        ]
        quintiles.append(
            SignalQuintile(
                quintile=index,
                n=len(bucket),
                mean_signal=(
                    sum(_signal_value(row, field) for row in bucket)
                    / len(bucket)
                ),
                brier_contribution=sum(briers) / len(bucket),
                log_loss_contribution=sum(log_losses) / len(bucket),
                mean_absolute_residual=sum(abs_residuals) / len(bucket),
                accuracy=sum(correct) / len(bucket),
            )
        )

    xs = [_signal_value(row, field) for row in available]
    brier_values = [_brier_contribution(row) for row in available]
    log_loss_values = [_log_loss_contribution(row) for row in available]
    abs_values = [
        abs(
            (1.0 if row.base.outcome_a else 0.0)
            - row.base.core_probability_a
        )
        for row in available
    ]
    q5_minus_q1_brier = None
    q5_minus_q1_log = None
    q5_minus_q1_abs = None
    if len(quintiles) >= 2:
        q5_minus_q1_brier = (
            quintiles[-1].brier_contribution
            - quintiles[0].brier_contribution
        )
        q5_minus_q1_log = (
            quintiles[-1].log_loss_contribution
            - quintiles[0].log_loss_contribution
        )
        q5_minus_q1_abs = (
            quintiles[-1].mean_absolute_residual
            - quintiles[0].mean_absolute_residual
        )
    return SignalDiagnostic(
        n=len(available),
        brier_slope=_linear_slope(xs, brier_values),
        log_loss_slope=_linear_slope(xs, log_loss_values),
        absolute_residual_slope=_linear_slope(xs, abs_values),
        q5_minus_q1_brier=q5_minus_q1_brier,
        q5_minus_q1_log_loss=q5_minus_q1_log,
        q5_minus_q1_absolute_residual=q5_minus_q1_abs,
        quintiles=tuple(quintiles),
    )


def _score_risk_rows(rows: list[_RiskRow]) -> Score:
    if not rows:
        raise ValueError("cannot score empty risk selection")
    outcomes = [row.distance.base.outcome_a for row in rows]
    probabilities = [row.distance.base.core_probability_a for row in rows]
    return Score(
        n=len(rows),
        brier=brier_score(outcomes, probabilities),
        log_loss=binary_log_loss(outcomes, probabilities),
        accuracy=accuracy(outcomes, probabilities),
        ece_10=expected_calibration_error(outcomes, probabilities, n_bins=10),
    )


def _selective_comparison(rows: list[_RiskRow]) -> SelectiveComparison:
    if not rows:
        raise ValueError("no OOS uncertainty-risk predictions are available")
    confidence_order = sorted(
        rows,
        key=lambda row: (
            -row.distance.base.core_confidence,
            row.distance.base.year,
            row.distance.base.match_id,
        ),
    )
    risk_order = sorted(
        rows,
        key=lambda row: (
            row.predicted_brier_risk,
            row.distance.base.year,
            row.distance.base.match_id,
        ),
    )
    total = len(rows)
    coverage_results: list[SelectiveCoverage] = []
    for coverage in _COVERAGE_LEVELS:
        keep = max(1, min(total, math.ceil(total * coverage)))
        baseline_score = _score_risk_rows(confidence_order[:keep])
        risk_score = _score_risk_rows(risk_order[:keep])
        coverage_results.append(
            SelectiveCoverage(
                requested_coverage=coverage,
                n=keep,
                realized_coverage=keep / total,
                confidence_baseline=baseline_score,
                uncertainty_model=risk_score,
                brier_improvement=baseline_score.brier - risk_score.brier,
                log_loss_improvement=(
                    baseline_score.log_loss - risk_score.log_loss
                ),
                accuracy_change=(
                    risk_score.accuracy - baseline_score.accuracy
                ),
            )
        )
    return SelectiveComparison(
        n=total,
        coverage=tuple(coverage_results),
    )


def _recent_distance_rows(rows: list[_DistanceRow]) -> list[_DistanceRow]:
    return [
        row
        for row in rows
        if _RECENT_START_YEAR <= row.base.year <= _RECENT_END_YEAR
    ]


def _recent_risk_rows(rows: list[_RiskRow]) -> list[_RiskRow]:
    return [
        row
        for row in rows
        if _RECENT_START_YEAR <= row.distance.base.year <= _RECENT_END_YEAR
    ]


def _positive_signal_pass(
    aggregate: SignalDiagnostic,
    recent: SignalDiagnostic | None,
    *,
    require_quintiles: bool,
) -> bool:
    if recent is None:
        return False
    required = [
        aggregate.brier_slope,
        aggregate.log_loss_slope,
        recent.brier_slope,
        recent.log_loss_slope,
    ]
    if any(value is None or value <= 0.0 for value in required):
        return False
    if require_quintiles:
        spreads = [
            aggregate.q5_minus_q1_brier,
            aggregate.q5_minus_q1_log_loss,
            recent.q5_minus_q1_brier,
            recent.q5_minus_q1_log_loss,
        ]
        if any(value is None or value <= 0.0 for value in spreads):
            return False
    return True


def _negative_signal_pass(
    aggregate: SignalDiagnostic,
    recent: SignalDiagnostic | None,
) -> bool:
    if recent is None:
        return False
    required = [
        aggregate.brier_slope,
        aggregate.log_loss_slope,
        recent.brier_slope,
        recent.log_loss_slope,
    ]
    return all(
        value is not None and value < 0.0
        for value in required
    )


def _coverage_map(
    comparison: SelectiveComparison,
) -> dict[float, SelectiveCoverage]:
    return {
        item.requested_coverage: item
        for item in comparison.coverage
    }


def _mean_operational_improvements(
    comparison: SelectiveComparison,
) -> tuple[int, int, float, float]:
    by_coverage = _coverage_map(comparison)
    selected = [
        by_coverage[value]
        for value in _PRIMARY_OPERATIONAL_COVERAGES
    ]
    brier_wins = sum(item.brier_improvement > 0.0 for item in selected)
    log_wins = sum(item.log_loss_improvement > 0.0 for item in selected)
    mean_brier = (
        sum(item.brier_improvement for item in selected)
        / len(selected)
    )
    mean_log = (
        sum(item.log_loss_improvement for item in selected)
        / len(selected)
    )
    return brier_wins, log_wins, mean_brier, mean_log


def _monotone_brier_through_25(
    comparison: SelectiveComparison,
) -> bool:
    by_coverage = _coverage_map(comparison)
    values = [
        by_coverage[coverage].uncertainty_model.brier
        for coverage in (1.0, 0.75, 0.50, 0.25)
    ]
    return all(
        later <= earlier + 1e-12
        for earlier, later in zip(values[:-1], values[1:], strict=True)
    )


def run_uncertainty_ood(
    matches: list[HistoricalMatch],
    *,
    tour: Tour,
    min_core_train_matches: int = 1000,
    min_neighbor_pool: int = 1000,
    min_condition_train_rows: int = 1000,
    min_risk_train_rows: int = 1000,
) -> UncertaintyOODReport:
    for name, value in (
        ("min_core_train_matches", min_core_train_matches),
        ("min_neighbor_pool", min_neighbor_pool),
        ("min_condition_train_rows", min_condition_train_rows),
        ("min_risk_train_rows", min_risk_train_rows),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    if min_neighbor_pool < _PRIMARY_K:
        raise ValueError("min_neighbor_pool must be at least k=100")

    base_rows = _aligned_base_rows(
        matches,
        tour=tour,
        min_core_train_matches=min_core_train_matches,
    )
    distance_rows = _build_distance_rows(
        base_rows,
        min_neighbor_pool=min_neighbor_pool,
    )
    if not distance_rows:
        raise ValueError("no historical distance rows are available")
    conditioned = _condition_distances(
        distance_rows,
        min_condition_train_rows=min_condition_train_rows,
    )
    if not conditioned:
        raise ValueError("no conditioned uncertainty rows are available")
    risk_rows = _build_risk_rows(
        conditioned,
        tour=tour,
        min_risk_train_rows=min_risk_train_rows,
    )
    if not risk_rows:
        raise ValueError("no OOS uncertainty-risk predictions are available")

    recent_conditioned_rows = _recent_distance_rows(conditioned)
    conditioned_diag = _signal_diagnostic(
        conditioned,
        field="conditioned_unfamiliarity",
    )
    recent_conditioned_diag = (
        _signal_diagnostic(
            recent_conditioned_rows,
            field="conditioned_unfamiliarity",
        )
        if recent_conditioned_rows
        else None
    )
    disagreement_diag = _signal_diagnostic(
        conditioned,
        field="disagreement",
    )
    recent_disagreement_diag = (
        _signal_diagnostic(
            recent_conditioned_rows,
            field="disagreement",
        )
        if recent_conditioned_rows
        else None
    )
    missing_diag = _signal_diagnostic(conditioned, field="missingness")
    recent_missing_diag = (
        _signal_diagnostic(recent_conditioned_rows, field="missingness")
        if recent_conditioned_rows
        else None
    )
    depth_diag = _signal_diagnostic(conditioned, field="history_depth")
    recent_depth_diag = (
        _signal_diagnostic(recent_conditioned_rows, field="history_depth")
        if recent_conditioned_rows
        else None
    )
    point_diag = None
    recent_point_diag = None
    if tour == "ATP":
        point_diag = _signal_diagnostic(conditioned, field="point_depth")
        recent_point_diag = (
            _signal_diagnostic(recent_conditioned_rows, field="point_depth")
            if recent_conditioned_rows
            else None
        )

    selective = _selective_comparison(risk_rows)
    recent_risk = _recent_risk_rows(risk_rows)
    recent_selective = (
        _selective_comparison(recent_risk)
        if recent_risk
        else None
    )

    brier_wins, log_wins, mean_brier, mean_log = (
        _mean_operational_improvements(selective)
    )
    recent_mean_brier = None
    recent_mean_log = None
    if recent_selective is not None:
        _, _, recent_mean_brier, recent_mean_log = (
            _mean_operational_improvements(recent_selective)
        )

    combined_pass = bool(
        brier_wins >= 2
        and log_wins >= 2
        and mean_brier > 0.0
        and mean_log > 0.0
        and recent_mean_brier is not None
        and recent_mean_brier > 0.0
        and recent_mean_log is not None
        and recent_mean_log > 0.0
        and _monotone_brier_through_25(selective)
    )

    ledger = tuple(
        PredictionLedgerRow(
            match_id=row.distance.base.match_id,
            year=row.distance.base.year,
            outcome_a=row.distance.base.outcome_a,
            core_probability_a=row.distance.base.core_probability_a,
            predicted_brier_risk=row.predicted_brier_risk,
            core_confidence=row.distance.base.core_confidence,
            conditioned_unfamiliarity=float(
                row.distance.conditioned_unfamiliarity
            ),
            disagreement=row.distance.base.disagreement,
            alignment_missing_fraction=(
                row.distance.base.alignment_vector.missing_fraction
            ),
            min_prior_matches=row.distance.base.min_prior_matches,
            min_prior_point_exposure=(
                row.distance.base.min_prior_point_exposure
            ),
            raw_mean_distance_100=row.distance.raw_mean_distance_100,
            historical_pool_size=row.distance.historical_pool_size,
        )
        for row in risk_rows
    )

    return UncertaintyOODReport(
        experiment_id="UNCERTAINTY-OOD-001",
        tour=tour,
        development_end_year=_DEVELOPMENT_END_YEAR,
        alignment_representation=(
            "full_genome"
            if tour == "ATP"
            else "strict_core_geometry"
        ),
        primary_k=_PRIMARY_K,
        min_core_train_matches=min_core_train_matches,
        min_neighbor_pool=min_neighbor_pool,
        min_condition_train_rows=min_condition_train_rows,
        min_risk_train_rows=min_risk_train_rows,
        distance_population_n=len(distance_rows),
        conditioned_population_n=len(conditioned),
        risk_population_n=len(risk_rows),
        conditioned_unfamiliarity=conditioned_diag,
        recent_conditioned_unfamiliarity=recent_conditioned_diag,
        disagreement=disagreement_diag,
        recent_disagreement=recent_disagreement_diag,
        missingness=missing_diag,
        recent_missingness=recent_missing_diag,
        history_depth=depth_diag,
        recent_history_depth=recent_depth_diag,
        point_depth=point_diag,
        recent_point_depth=recent_point_diag,
        selective=selective,
        recent_selective=recent_selective,
        promotion_diagnostics=PromotionDiagnostics(
            conditioned_density_pass=_positive_signal_pass(
                conditioned_diag,
                recent_conditioned_diag,
                require_quintiles=True,
            ),
            disagreement_pass=_positive_signal_pass(
                disagreement_diag,
                recent_disagreement_diag,
                require_quintiles=True,
            ),
            missingness_pass=_positive_signal_pass(
                missing_diag,
                recent_missing_diag,
                require_quintiles=False,
            ),
            history_depth_pass=_negative_signal_pass(
                depth_diag,
                recent_depth_diag,
            ),
            point_depth_pass=(
                _negative_signal_pass(
                    point_diag,
                    recent_point_diag,
                )
                if point_diag is not None
                else None
            ),
            operational_brier_win_count=brier_wins,
            operational_log_loss_win_count=log_wins,
            operational_coverage_count=len(
                _PRIMARY_OPERATIONAL_COVERAGES
            ),
            mean_operational_brier_improvement=mean_brier,
            mean_operational_log_loss_improvement=mean_log,
            recent_mean_operational_brier_improvement=recent_mean_brier,
            recent_mean_operational_log_loss_improvement=recent_mean_log,
            monotone_uncertainty_brier_through_25pct=(
                _monotone_brier_through_25(selective)
            ),
            combined_uncertainty_pass=combined_pass,
        ),
        predictions=ledger,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run UNCERTAINTY-OOD-001 on frozen 2000-2025 development data"
        )
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--tour", required=True, choices=("ATP", "WTA"))
    parser.add_argument("--min-core-train-matches", type=int, default=1000)
    parser.add_argument("--min-neighbor-pool", type=int, default=1000)
    parser.add_argument("--min-condition-train-rows", type=int, default=1000)
    parser.add_argument("--min-risk-train-rows", type=int, default=1000)
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
    report = run_uncertainty_ood(
        matches,
        tour=args.tour,
        min_core_train_matches=args.min_core_train_matches,
        min_neighbor_pool=args.min_neighbor_pool,
        min_condition_train_rows=args.min_condition_train_rows,
        min_risk_train_rows=args.min_risk_train_rows,
    )
    print(json.dumps(asdict(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
