from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from math import log
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
from tennis_genome.features.foundational import (
    FoundationalSnapshot,
    walk_forward_foundational_features,
)
from tennis_genome.features.genome import (
    GENOME_VERSION,
    GenomeVector,
    build_genome_vector,
    canonical_outcome,
    canonical_probability,
    original_probability,
)
from tennis_genome.models.core_v1_spec import strict_a_features
from tennis_genome.models.feature_probability import FeatureProbabilityModel
from tennis_genome.neighbors.historical import HistoricalGenomeIndex, ResidualRecord
from tennis_genome.profiles.state import MatchProfilePair, walk_forward_player_profiles

_DEVELOPMENT_END_YEAR = 2025
_RECENT_START_YEAR = 2021
_RECENT_END_YEAR = 2025
_PRIMARY_K = 100
_SECONDARY_K = (25, 250)
_CANDIDATE_LIMIT = 1000


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
    raw_core: ModelScore
    meta_control: ModelScore
    genome_challenger: ModelScore
    brier_improvement: float
    log_loss_improvement: float
    accuracy_change: float


@dataclass(frozen=True)
class YearComparison:
    year: int
    comparison: ModelComparison
    joint_genome_win: bool


@dataclass(frozen=True)
class SignalQuintile:
    quintile: int
    n: int
    mean_neighbor_residual: float
    mean_realized_core_residual: float


@dataclass(frozen=True)
class SignalDiagnostic:
    n: int
    residual_slope_on_neighbor_signal: float | None
    top_minus_bottom_core_residual: float | None
    quintiles: tuple[SignalQuintile, ...]


@dataclass(frozen=True)
class KSignalDiagnostic:
    k: int
    diagnostic: SignalDiagnostic


@dataclass(frozen=True)
class DensityQuintile:
    quintile: int
    n: int
    mean_distance: float
    core_brier_contribution: float
    core_log_loss_contribution: float
    core_accuracy: float
    mean_absolute_core_residual: float


@dataclass(frozen=True)
class DensityDiagnostic:
    n: int
    log_loss_slope_on_distance: float | None
    absolute_residual_slope_on_distance: float | None
    top_minus_bottom_log_loss: float | None
    quintiles: tuple[DensityQuintile, ...]


@dataclass(frozen=True)
class SharedPlayerSensitivity:
    eligible_neighbor_rows: int
    primary_neighbor_rows: int
    coverage: float
    comparison: ModelComparison | None
    recent_comparison: ModelComparison | None
    yearly: tuple[YearComparison, ...]
    residual: SignalDiagnostic
    recent_residual: SignalDiagnostic | None


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
    residual_slope_positive: bool
    residual_top_minus_bottom_positive: bool
    recent_residual_direction_not_reversed: bool | None
    h011_primary_pass: bool
    shared_player_classification: str
    density_log_loss_slope_positive: bool
    density_absolute_residual_slope_positive: bool
    density_top_minus_bottom_log_loss_positive: bool
    recent_density_direction_not_reversed: bool | None
    h012_density_pass: bool


@dataclass(frozen=True)
class PredictionLedgerRow:
    match_id: str
    year: int
    core_probability_a: float
    meta_control_probability_a: float
    genome_probability_a: float
    outcome_a: bool
    neighbor_residual_100: float
    mean_distance_100: float
    kth_distance_100: float
    shared_player_fraction_100: float
    genome_missing_fraction: float
    neighbor_ids_digest_100: str
    nonsharing_neighbor_ids_digest_100: str | None


@dataclass(frozen=True)
class GenomeNeighborReport:
    experiment_id: str
    tour: Tour
    genome_version: str
    feature_names: tuple[str, ...]
    min_core_train_matches: int
    min_neighbor_pool: int
    min_meta_train_rows: int
    primary_k: int
    secondary_k: tuple[int, ...]
    candidate_limit: int
    neighbor_population_n: int
    meta_population_n: int
    comparison: ModelComparison
    recent_comparison: ModelComparison | None
    yearly: tuple[YearComparison, ...]
    residual: SignalDiagnostic
    recent_residual: SignalDiagnostic | None
    secondary_k_diagnostics: tuple[KSignalDiagnostic, ...]
    density: DensityDiagnostic
    recent_density: DensityDiagnostic | None
    shared_player_sensitivity: SharedPlayerSensitivity
    promotion_diagnostics: PromotionDiagnostics
    predictions: tuple[PredictionLedgerRow, ...]


@dataclass(frozen=True)
class _CoreLedgerRow:
    match_id: str
    year: int
    outcome_a: bool
    outcome_favorite: bool
    core_probability_a: float
    core_probability_favorite: float
    core_residual_favorite: float
    genome: GenomeVector


@dataclass(frozen=True)
class _NeighborEvidenceRow:
    match_id: str
    year: int
    outcome_a: bool
    outcome_favorite: bool
    orientation_sign: int
    core_probability_a: float
    core_probability_favorite: float
    core_residual_favorite: float
    neighbor_residual_25: float
    neighbor_residual_100: float
    neighbor_residual_250: float
    nearest_distance_100: float
    mean_distance_100: float
    kth_distance_100: float
    shared_player_fraction_100: float
    nonsharing_neighbor_residual_100: float | None
    genome_missing_fraction: float
    neighbor_ids_digest_100: str
    nonsharing_neighbor_ids_digest_100: str | None


@dataclass(frozen=True)
class _MetaPredictionRow:
    match_id: str
    year: int
    outcome_a: bool
    core_probability_a: float
    meta_control_probability_a: float
    genome_probability_a: float


def _score(rows: list[_MetaPredictionRow], probability_field: str) -> ModelScore:
    if not rows:
        raise ValueError("cannot score an empty prediction population")
    y_true = [row.outcome_a for row in rows]
    probabilities = [float(getattr(row, probability_field)) for row in rows]
    return ModelScore(
        n=len(rows),
        brier=brier_score(y_true, probabilities),
        log_loss=binary_log_loss(y_true, probabilities),
        accuracy=accuracy(y_true, probabilities),
        ece_10=expected_calibration_error(y_true, probabilities, n_bins=10),
    )


def _comparison(rows: list[_MetaPredictionRow]) -> ModelComparison:
    raw_core = _score(rows, "core_probability_a")
    control = _score(rows, "meta_control_probability_a")
    challenger = _score(rows, "genome_probability_a")
    return ModelComparison(
        n=len(rows),
        raw_core=raw_core,
        meta_control=control,
        genome_challenger=challenger,
        brier_improvement=control.brier - challenger.brier,
        log_loss_improvement=control.log_loss - challenger.log_loss,
        accuracy_change=challenger.accuracy - control.accuracy,
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
            "GENOME-NN-001 is frozen to 2000-2025 development data; "
            "post-2025 matches, including the spent 2026 holdout, are forbidden"
        )
    return [
        match
        for match in tour_matches
        if not match.outcome.walkover and (not exclude_retirements or not match.outcome.retirement)
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


def _build_core_ledger(
    matches: list[HistoricalMatch],
    *,
    tour: Tour,
    min_core_train_matches: int,
) -> list[_CoreLedgerRow]:
    pairs, foundational, outcomes = _aligned_state(matches)
    genomes = {
        pair.match_id: build_genome_vector(pair, foundational[pair.match_id]) for pair in pairs
    }
    years = sorted({pair.event_date.year for pair in pairs})
    rows: list[_CoreLedgerRow] = []

    for test_year in years:
        train_pairs = [pair for pair in pairs if pair.event_date.year < test_year]
        test_pairs = [pair for pair in pairs if pair.event_date.year == test_year]
        if len(train_pairs) < min_core_train_matches or not test_pairs:
            continue
        y_train = [outcomes[pair.match_id] for pair in train_pairs]
        if len(set(y_train)) < 2:
            continue

        model = FeatureProbabilityModel(strict_a_features(tour)).fit(
            [foundational[pair.match_id] for pair in train_pairs],
            y_train,
        )
        probabilities = model.predict_probabilities(
            [foundational[pair.match_id] for pair in test_pairs]
        )
        for pair, probability_a in zip(test_pairs, probabilities, strict=True):
            genome = genomes[pair.match_id]
            outcome_a = outcomes[pair.match_id]
            probability_favorite = canonical_probability(
                probability_a,
                orientation_sign=genome.orientation_sign,
            )
            outcome_favorite = canonical_outcome(
                outcome_a,
                orientation_sign=genome.orientation_sign,
            )
            rows.append(
                _CoreLedgerRow(
                    match_id=pair.match_id,
                    year=test_year,
                    outcome_a=outcome_a,
                    outcome_favorite=outcome_favorite,
                    core_probability_a=probability_a,
                    core_probability_favorite=probability_favorite,
                    core_residual_favorite=(
                        (1.0 if outcome_favorite else 0.0) - probability_favorite
                    ),
                    genome=genome,
                )
            )
    return rows


def _ids_digest(ids: tuple[str, ...]) -> str:
    raw = "\n".join(ids).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _build_neighbor_evidence(
    ledger: list[_CoreLedgerRow],
    *,
    min_neighbor_pool: int,
    candidate_limit: int,
) -> list[_NeighborEvidenceRow]:
    years = sorted({row.year for row in ledger})
    evidence: list[_NeighborEvidenceRow] = []

    for test_year in years:
        historical = [row for row in ledger if row.year < test_year]
        targets = [row for row in ledger if row.year == test_year]
        if len(historical) < min_neighbor_pool or not targets:
            continue
        if any(row.year >= test_year for row in historical):
            raise RuntimeError("future/non-historical row entered Genome neighbor pool")

        index = HistoricalGenomeIndex(
            [
                ResidualRecord(
                    genome=row.genome,
                    residual_favorite=row.core_residual_favorite,
                )
                for row in historical
            ]
        )
        candidate_sets = index.query_candidates(
            [row.genome for row in targets],
            candidate_limit=candidate_limit,
        )

        for row, candidates in zip(targets, candidate_sets, strict=True):
            summary_25 = index.summarize(row.genome, candidates, k=25)
            summary_100 = index.summarize(row.genome, candidates, k=_PRIMARY_K)
            summary_250 = index.summarize(row.genome, candidates, k=250)
            if summary_25 is None or summary_100 is None or summary_250 is None:
                raise RuntimeError("registered Genome k is unavailable despite pool gate")
            nonsharing = index.summarize(
                row.genome,
                candidates,
                k=_PRIMARY_K,
                exclude_shared_players=True,
            )
            evidence.append(
                _NeighborEvidenceRow(
                    match_id=row.match_id,
                    year=row.year,
                    outcome_a=row.outcome_a,
                    outcome_favorite=row.outcome_favorite,
                    orientation_sign=row.genome.orientation_sign,
                    core_probability_a=row.core_probability_a,
                    core_probability_favorite=row.core_probability_favorite,
                    core_residual_favorite=row.core_residual_favorite,
                    neighbor_residual_25=summary_25.mean_residual,
                    neighbor_residual_100=summary_100.mean_residual,
                    neighbor_residual_250=summary_250.mean_residual,
                    nearest_distance_100=summary_100.nearest_distance,
                    mean_distance_100=summary_100.mean_distance,
                    kth_distance_100=summary_100.kth_distance,
                    shared_player_fraction_100=(summary_100.shared_player_fraction),
                    nonsharing_neighbor_residual_100=(
                        None if nonsharing is None else nonsharing.mean_residual
                    ),
                    genome_missing_fraction=row.genome.missing_fraction,
                    neighbor_ids_digest_100=_ids_digest(summary_100.neighbor_ids),
                    nonsharing_neighbor_ids_digest_100=(
                        None if nonsharing is None else _ids_digest(nonsharing.neighbor_ids)
                    ),
                )
            )
    return evidence


def _logit_probability(probability: float) -> float:
    clipped = min(max(float(probability), 1e-9), 1.0 - 1e-9)
    return log(clipped / (1.0 - clipped))


def _meta_predictions(
    evidence: list[_NeighborEvidenceRow],
    *,
    signal_field: str,
    min_meta_train_rows: int,
) -> tuple[list[_MetaPredictionRow], tuple[YearComparison, ...]]:
    available = [row for row in evidence if getattr(row, signal_field) is not None]
    years = sorted({row.year for row in available})
    predictions: list[_MetaPredictionRow] = []
    yearly: list[YearComparison] = []

    for test_year in years:
        train = [row for row in available if row.year < test_year]
        test = [row for row in available if row.year == test_year]
        if len(train) < min_meta_train_rows or not test:
            continue
        y_train = [int(row.outcome_favorite) for row in train]
        if len(set(y_train)) < 2:
            continue

        control = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000),
        )
        challenger = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000),
        )
        control.fit(
            [[_logit_probability(row.core_probability_favorite)] for row in train],
            y_train,
        )
        challenger.fit(
            [
                [
                    _logit_probability(row.core_probability_favorite),
                    float(getattr(row, signal_field)),
                ]
                for row in train
            ],
            y_train,
        )
        control_favorite = control.predict_proba(
            [[_logit_probability(row.core_probability_favorite)] for row in test]
        )[:, 1].tolist()
        challenger_favorite = challenger.predict_proba(
            [
                [
                    _logit_probability(row.core_probability_favorite),
                    float(getattr(row, signal_field)),
                ]
                for row in test
            ]
        )[:, 1].tolist()

        year_predictions: list[_MetaPredictionRow] = []
        for row, control_probability, challenger_probability in zip(
            test,
            control_favorite,
            challenger_favorite,
            strict=True,
        ):
            year_predictions.append(
                _MetaPredictionRow(
                    match_id=row.match_id,
                    year=row.year,
                    outcome_a=row.outcome_a,
                    core_probability_a=row.core_probability_a,
                    meta_control_probability_a=original_probability(
                        control_probability,
                        orientation_sign=row.orientation_sign,
                    ),
                    genome_probability_a=original_probability(
                        challenger_probability,
                        orientation_sign=row.orientation_sign,
                    ),
                )
            )
        comparison = _comparison(year_predictions)
        yearly.append(
            YearComparison(
                year=test_year,
                comparison=comparison,
                joint_genome_win=(
                    comparison.genome_challenger.brier < comparison.meta_control.brier
                    and comparison.genome_challenger.log_loss < comparison.meta_control.log_loss
                ),
            )
        )
        predictions.extend(year_predictions)
    return predictions, tuple(yearly)


def _linear_slope(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or not xs:
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((value - mean_x) ** 2 for value in xs)
    if denominator <= 0.0:
        return None
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    return numerator / denominator


def _equal_count_quintiles(
    rows: list[_NeighborEvidenceRow],
    *,
    value_field: str,
) -> list[list[_NeighborEvidenceRow]]:
    ordered = sorted(
        rows,
        key=lambda row: (float(getattr(row, value_field)), row.match_id),
    )
    buckets: list[list[_NeighborEvidenceRow]] = [[] for _ in range(5)]
    total = len(ordered)
    for rank, row in enumerate(ordered):
        bucket = min((rank * 5) // total, 4)
        buckets[bucket].append(row)
    return buckets


def _signal_diagnostic(
    rows: list[_NeighborEvidenceRow],
    *,
    signal_field: str,
) -> SignalDiagnostic:
    available = [row for row in rows if getattr(row, signal_field) is not None]
    if not available:
        return SignalDiagnostic(
            n=0,
            residual_slope_on_neighbor_signal=None,
            top_minus_bottom_core_residual=None,
            quintiles=(),
        )
    buckets = _equal_count_quintiles(available, value_field=signal_field)
    quintiles: list[SignalQuintile] = []
    for index, bucket in enumerate(buckets, start=1):
        if not bucket:
            continue
        quintiles.append(
            SignalQuintile(
                quintile=index,
                n=len(bucket),
                mean_neighbor_residual=(
                    sum(float(getattr(row, signal_field)) for row in bucket) / len(bucket)
                ),
                mean_realized_core_residual=(
                    sum(row.core_residual_favorite for row in bucket) / len(bucket)
                ),
            )
        )
    top_minus_bottom = None
    if len(quintiles) >= 2:
        top_minus_bottom = (
            quintiles[-1].mean_realized_core_residual - quintiles[0].mean_realized_core_residual
        )
    return SignalDiagnostic(
        n=len(available),
        residual_slope_on_neighbor_signal=_linear_slope(
            [float(getattr(row, signal_field)) for row in available],
            [row.core_residual_favorite for row in available],
        ),
        top_minus_bottom_core_residual=top_minus_bottom,
        quintiles=tuple(quintiles),
    )


def _core_log_loss_contribution(row: _NeighborEvidenceRow) -> float:
    probability = min(
        max(row.core_probability_favorite, 1e-15),
        1.0 - 1e-15,
    )
    return -log(probability if row.outcome_favorite else 1.0 - probability)


def _density_diagnostic(rows: list[_NeighborEvidenceRow]) -> DensityDiagnostic:
    if not rows:
        return DensityDiagnostic(
            n=0,
            log_loss_slope_on_distance=None,
            absolute_residual_slope_on_distance=None,
            top_minus_bottom_log_loss=None,
            quintiles=(),
        )
    buckets = _equal_count_quintiles(rows, value_field="mean_distance_100")
    quintiles: list[DensityQuintile] = []
    for index, bucket in enumerate(buckets, start=1):
        if not bucket:
            continue
        brier_values = [
            (row.core_probability_favorite - (1.0 if row.outcome_favorite else 0.0)) ** 2
            for row in bucket
        ]
        log_losses = [_core_log_loss_contribution(row) for row in bucket]
        quintiles.append(
            DensityQuintile(
                quintile=index,
                n=len(bucket),
                mean_distance=(sum(row.mean_distance_100 for row in bucket) / len(bucket)),
                core_brier_contribution=sum(brier_values) / len(bucket),
                core_log_loss_contribution=sum(log_losses) / len(bucket),
                core_accuracy=(
                    sum(
                        (row.core_probability_favorite >= 0.5) == row.outcome_favorite
                        for row in bucket
                    )
                    / len(bucket)
                ),
                mean_absolute_core_residual=(
                    sum(abs(row.core_residual_favorite) for row in bucket) / len(bucket)
                ),
            )
        )
    top_minus_bottom = None
    if len(quintiles) >= 2:
        top_minus_bottom = (
            quintiles[-1].core_log_loss_contribution - quintiles[0].core_log_loss_contribution
        )
    return DensityDiagnostic(
        n=len(rows),
        log_loss_slope_on_distance=_linear_slope(
            [row.mean_distance_100 for row in rows],
            [_core_log_loss_contribution(row) for row in rows],
        ),
        absolute_residual_slope_on_distance=_linear_slope(
            [row.mean_distance_100 for row in rows],
            [abs(row.core_residual_favorite) for row in rows],
        ),
        top_minus_bottom_log_loss=top_minus_bottom,
        quintiles=tuple(quintiles),
    )


def _recent_rows(rows: list[_NeighborEvidenceRow]) -> list[_NeighborEvidenceRow]:
    return [row for row in rows if _RECENT_START_YEAR <= row.year <= _RECENT_END_YEAR]


def _recent_predictions(rows: list[_MetaPredictionRow]) -> list[_MetaPredictionRow]:
    return [row for row in rows if _RECENT_START_YEAR <= row.year <= _RECENT_END_YEAR]


def _shared_player_sensitivity(
    evidence: list[_NeighborEvidenceRow],
    *,
    min_meta_train_rows: int,
) -> SharedPlayerSensitivity:
    eligible = [row for row in evidence if row.nonsharing_neighbor_residual_100 is not None]
    predictions, yearly = _meta_predictions(
        eligible,
        signal_field="nonsharing_neighbor_residual_100",
        min_meta_train_rows=min_meta_train_rows,
    )
    recent_predictions = _recent_predictions(predictions)
    recent_eligible = _recent_rows(eligible)
    return SharedPlayerSensitivity(
        eligible_neighbor_rows=len(eligible),
        primary_neighbor_rows=len(evidence),
        coverage=(len(eligible) / len(evidence) if evidence else 0.0),
        comparison=_comparison(predictions) if predictions else None,
        recent_comparison=(_comparison(recent_predictions) if recent_predictions else None),
        yearly=yearly,
        residual=_signal_diagnostic(
            eligible,
            signal_field="nonsharing_neighbor_residual_100",
        ),
        recent_residual=(
            _signal_diagnostic(
                recent_eligible,
                signal_field="nonsharing_neighbor_residual_100",
            )
            if recent_eligible
            else None
        ),
    )


def _shared_classification(
    *,
    primary_pass: bool,
    sensitivity: SharedPlayerSensitivity,
) -> str:
    if not primary_pass:
        return "primary_failed"
    if sensitivity.coverage < 0.80:
        return "transferability_inconclusive"
    if sensitivity.comparison is None:
        return "transferability_inconclusive"
    if (
        sensitivity.comparison.brier_improvement > 0.0
        and sensitivity.comparison.log_loss_improvement > 0.0
    ):
        return "general_historical_alignment_candidate"
    return "identity_dependent_conditional"


def run_genome_neighborhood(
    matches: list[HistoricalMatch],
    *,
    tour: Tour,
    min_core_train_matches: int = 1000,
    min_neighbor_pool: int = 1000,
    min_meta_train_rows: int = 1000,
    candidate_limit: int = _CANDIDATE_LIMIT,
    exclude_retirements: bool = True,
) -> GenomeNeighborReport:
    """Run preregistered GENOME-NN-001 without future or in-sample residuals."""
    for name, value in (
        ("min_core_train_matches", min_core_train_matches),
        ("min_neighbor_pool", min_neighbor_pool),
        ("min_meta_train_rows", min_meta_train_rows),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    if candidate_limit < 250:
        raise ValueError("candidate_limit must be at least 250")

    eligible = _eligible_matches(
        matches,
        tour=tour,
        exclude_retirements=exclude_retirements,
    )
    core_ledger = _build_core_ledger(
        eligible,
        tour=tour,
        min_core_train_matches=min_core_train_matches,
    )
    evidence = _build_neighbor_evidence(
        core_ledger,
        min_neighbor_pool=min_neighbor_pool,
        candidate_limit=candidate_limit,
    )
    if not evidence:
        raise ValueError("no historical Genome neighborhoods are available")

    predictions, yearly = _meta_predictions(
        evidence,
        signal_field="neighbor_residual_100",
        min_meta_train_rows=min_meta_train_rows,
    )
    if not predictions:
        raise ValueError("no chronological Genome meta-predictions are available")

    comparison = _comparison(predictions)
    recent_predictions = _recent_predictions(predictions)
    recent_comparison = _comparison(recent_predictions) if recent_predictions else None
    residual = _signal_diagnostic(
        evidence,
        signal_field="neighbor_residual_100",
    )
    recent_evidence = _recent_rows(evidence)
    recent_residual = (
        _signal_diagnostic(
            recent_evidence,
            signal_field="neighbor_residual_100",
        )
        if recent_evidence
        else None
    )
    density = _density_diagnostic(evidence)
    recent_density = _density_diagnostic(recent_evidence) if recent_evidence else None
    shared = _shared_player_sensitivity(
        evidence,
        min_meta_train_rows=min_meta_train_rows,
    )

    joint_wins = sum(item.joint_genome_win for item in yearly)
    joint_win_rate = joint_wins / len(yearly) if yearly else 0.0
    recent_brier_ok = (
        recent_comparison.genome_challenger.brier <= recent_comparison.meta_control.brier
        if recent_comparison is not None
        else None
    )
    recent_log_loss_ok = (
        recent_comparison.genome_challenger.log_loss <= recent_comparison.meta_control.log_loss
        if recent_comparison is not None
        else None
    )
    residual_slope_positive = bool(
        residual.residual_slope_on_neighbor_signal is not None
        and residual.residual_slope_on_neighbor_signal > 0.0
    )
    residual_spread_positive = bool(
        residual.top_minus_bottom_core_residual is not None
        and residual.top_minus_bottom_core_residual > 0.0
    )
    recent_residual_direction = (
        bool(
            recent_residual.residual_slope_on_neighbor_signal is not None
            and recent_residual.residual_slope_on_neighbor_signal >= 0.0
            and recent_residual.top_minus_bottom_core_residual is not None
            and recent_residual.top_minus_bottom_core_residual >= 0.0
        )
        if recent_residual is not None
        else None
    )
    primary_pass = bool(
        comparison.brier_improvement > 0.0
        and comparison.log_loss_improvement > 0.0
        and joint_win_rate >= 0.60
        and recent_brier_ok is True
        and recent_log_loss_ok is True
        and residual_slope_positive
        and residual_spread_positive
        and recent_residual_direction is True
    )

    density_log_slope_positive = bool(
        density.log_loss_slope_on_distance is not None and density.log_loss_slope_on_distance > 0.0
    )
    density_abs_slope_positive = bool(
        density.absolute_residual_slope_on_distance is not None
        and density.absolute_residual_slope_on_distance > 0.0
    )
    density_spread_positive = bool(
        density.top_minus_bottom_log_loss is not None and density.top_minus_bottom_log_loss > 0.0
    )
    recent_density_direction = (
        bool(
            recent_density.log_loss_slope_on_distance is not None
            and recent_density.log_loss_slope_on_distance >= 0.0
            and recent_density.absolute_residual_slope_on_distance is not None
            and recent_density.absolute_residual_slope_on_distance >= 0.0
            and recent_density.top_minus_bottom_log_loss is not None
            and recent_density.top_minus_bottom_log_loss >= 0.0
        )
        if recent_density is not None
        else None
    )
    density_pass = bool(
        density_log_slope_positive
        and density_abs_slope_positive
        and density_spread_positive
        and recent_density_direction is True
    )

    evidence_by_id = {row.match_id: row for row in evidence}
    prediction_ledger = tuple(
        PredictionLedgerRow(
            match_id=row.match_id,
            year=row.year,
            core_probability_a=row.core_probability_a,
            meta_control_probability_a=row.meta_control_probability_a,
            genome_probability_a=row.genome_probability_a,
            outcome_a=row.outcome_a,
            neighbor_residual_100=evidence_by_id[row.match_id].neighbor_residual_100,
            mean_distance_100=evidence_by_id[row.match_id].mean_distance_100,
            kth_distance_100=evidence_by_id[row.match_id].kth_distance_100,
            shared_player_fraction_100=(evidence_by_id[row.match_id].shared_player_fraction_100),
            genome_missing_fraction=(evidence_by_id[row.match_id].genome_missing_fraction),
            neighbor_ids_digest_100=(evidence_by_id[row.match_id].neighbor_ids_digest_100),
            nonsharing_neighbor_ids_digest_100=(
                evidence_by_id[row.match_id].nonsharing_neighbor_ids_digest_100
            ),
        )
        for row in predictions
    )

    secondary = tuple(
        KSignalDiagnostic(
            k=k,
            diagnostic=_signal_diagnostic(
                evidence,
                signal_field=f"neighbor_residual_{k}",
            ),
        )
        for k in _SECONDARY_K
    )
    feature_names = core_ledger[0].genome.feature_names if core_ledger else ()
    return GenomeNeighborReport(
        experiment_id="GENOME-NN-001",
        tour=tour,
        genome_version=GENOME_VERSION,
        feature_names=feature_names,
        min_core_train_matches=min_core_train_matches,
        min_neighbor_pool=min_neighbor_pool,
        min_meta_train_rows=min_meta_train_rows,
        primary_k=_PRIMARY_K,
        secondary_k=_SECONDARY_K,
        candidate_limit=candidate_limit,
        neighbor_population_n=len(evidence),
        meta_population_n=len(predictions),
        comparison=comparison,
        recent_comparison=recent_comparison,
        yearly=yearly,
        residual=residual,
        recent_residual=recent_residual,
        secondary_k_diagnostics=secondary,
        density=density,
        recent_density=recent_density,
        shared_player_sensitivity=shared,
        promotion_diagnostics=PromotionDiagnostics(
            aggregate_brier_positive=comparison.brier_improvement > 0.0,
            aggregate_log_loss_positive=comparison.log_loss_improvement > 0.0,
            joint_year_win_count=joint_wins,
            evaluated_year_count=len(yearly),
            joint_year_win_rate=joint_win_rate,
            at_least_60_percent_joint_year_wins=joint_win_rate >= 0.60,
            recent_brier_not_worse=recent_brier_ok,
            recent_log_loss_not_worse=recent_log_loss_ok,
            residual_slope_positive=residual_slope_positive,
            residual_top_minus_bottom_positive=residual_spread_positive,
            recent_residual_direction_not_reversed=recent_residual_direction,
            h011_primary_pass=primary_pass,
            shared_player_classification=_shared_classification(
                primary_pass=primary_pass,
                sensitivity=shared,
            ),
            density_log_loss_slope_positive=density_log_slope_positive,
            density_absolute_residual_slope_positive=density_abs_slope_positive,
            density_top_minus_bottom_log_loss_positive=density_spread_positive,
            recent_density_direction_not_reversed=recent_density_direction,
            h012_density_pass=density_pass,
        ),
        predictions=prediction_ledger,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run GENOME-NN-001 on frozen 2000-2025 development data"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--tour", required=True, choices=("ATP", "WTA"))
    parser.add_argument("--min-core-train-matches", type=int, default=1000)
    parser.add_argument("--min-neighbor-pool", type=int, default=1000)
    parser.add_argument("--min-meta-train-rows", type=int, default=1000)
    parser.add_argument("--candidate-limit", type=int, default=_CANDIDATE_LIMIT)
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
    report = run_genome_neighborhood(
        matches,
        tour=args.tour,
        min_core_train_matches=args.min_core_train_matches,
        min_neighbor_pool=args.min_neighbor_pool,
        min_meta_train_rows=args.min_meta_train_rows,
        candidate_limit=args.candidate_limit,
        exclude_retirements=not args.include_retirements,
    )
    print(json.dumps(asdict(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
