from __future__ import annotations

import argparse
import json
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
from tennis_genome.experiments.genome_neighborhood import (
    _build_core_ledger,
    _eligible_matches,
    _linear_slope,
    _logit_probability,
)
from tennis_genome.features.genome import GENOME_VERSION, GenomeVector, original_probability
from tennis_genome.neighbors.historical import HistoricalGenomeIndex, ResidualRecord

_DEVELOPMENT_END_YEAR = 2025
_RECENT_START_YEAR = 2021
_RECENT_END_YEAR = 2025
_PRIMARY_K = 100
_CANDIDATE_LIMIT = 1000


@dataclass(frozen=True)
class ModelScore:
    n: int
    brier: float
    log_loss: float
    accuracy: float
    ece_10: float


@dataclass(frozen=True)
class FourModelComparison:
    n: int
    calibration_control: ModelScore
    probability_neighborhood: ModelScore
    core_neighborhood: ModelScore
    full_genome: ModelScore
    full_vs_probability_brier_improvement: float
    full_vs_probability_log_loss_improvement: float
    full_vs_core_brier_improvement: float
    full_vs_core_log_loss_improvement: float


@dataclass(frozen=True)
class YearComparison:
    year: int
    comparison: FourModelComparison
    full_joint_win_vs_probability: bool
    full_joint_win_vs_core: bool


@dataclass(frozen=True)
class SignalQuintile:
    quintile: int
    n: int
    mean_signal: float
    mean_realized_core_residual: float


@dataclass(frozen=True)
class SignalDiagnostic:
    n: int
    residual_slope_on_signal: float | None
    top_minus_bottom_core_residual: float | None
    quintiles: tuple[SignalQuintile, ...]


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
class PromotionDiagnostics:
    gate_a_full_vs_probability: GateResult
    gate_b_full_vs_core: GateResult
    interpretation_class: str


@dataclass(frozen=True)
class PredictionRow:
    match_id: str
    year: int
    outcome_a: bool
    core_probability_a: float
    calibration_control_probability_a: float
    probability_neighborhood_probability_a: float
    core_neighborhood_probability_a: float
    full_genome_probability_a: float
    probability_neighbor_residual: float
    core_neighbor_residual: float
    full_neighbor_residual: float


@dataclass(frozen=True)
class GenomeAdversarialReport:
    experiment_id: str
    tour: Tour
    development_end_year: int
    genome_version: str
    primary_k: int
    candidate_limit: int
    min_core_train_matches: int
    min_neighbor_pool: int
    min_meta_train_rows: int
    neighbor_population_n: int
    meta_population_n: int
    comparison: FourModelComparison
    recent_comparison: FourModelComparison | None
    yearly: tuple[YearComparison, ...]
    probability_signal: SignalDiagnostic
    core_signal: SignalDiagnostic
    full_genome_signal: SignalDiagnostic
    recent_probability_signal: SignalDiagnostic | None
    recent_core_signal: SignalDiagnostic | None
    recent_full_genome_signal: SignalDiagnostic | None
    promotion_diagnostics: PromotionDiagnostics
    predictions: tuple[PredictionRow, ...]


@dataclass(frozen=True)
class _ControlEvidenceRow:
    match_id: str
    year: int
    outcome_a: bool
    outcome_favorite: bool
    orientation_sign: int
    core_probability_a: float
    core_probability_favorite: float
    core_residual_favorite: float
    probability_neighbor_residual: float
    core_neighbor_residual: float
    full_neighbor_residual: float


@dataclass(frozen=True)
class _MetaPredictionRow:
    match_id: str
    year: int
    outcome_a: bool
    core_probability_a: float
    calibration_control_probability_a: float
    probability_neighborhood_probability_a: float
    core_neighborhood_probability_a: float
    full_genome_probability_a: float


def _project_genome(
    genome: GenomeVector,
    *,
    feature_prefix: str,
) -> GenomeVector:
    indexes = [
        index
        for index, name in enumerate(genome.feature_names)
        if name.startswith(feature_prefix)
    ]
    if not indexes:
        raise ValueError(f"Genome has no features with prefix {feature_prefix!r}")
    return GenomeVector(
        match_id=genome.match_id,
        event_date=genome.event_date,
        tour=genome.tour,
        player_a_id=genome.player_a_id,
        player_b_id=genome.player_b_id,
        orientation_sign=genome.orientation_sign,
        feature_names=tuple(genome.feature_names[index] for index in indexes),
        values=tuple(genome.values[index] for index in indexes),
        feature_version=f"{genome.feature_version}:{feature_prefix.rstrip(':')}",
    )


def _probability_genome(row: object) -> GenomeVector:
    genome = row.genome
    return GenomeVector(
        match_id=genome.match_id,
        event_date=genome.event_date,
        tour=genome.tour,
        player_a_id=genome.player_a_id,
        player_b_id=genome.player_b_id,
        orientation_sign=genome.orientation_sign,
        feature_names=("core_probability_logit",),
        values=(_logit_probability(row.core_probability_favorite),),
        feature_version="genome-adv-v1-core-probability-only",
    )


def _core_genome(row: object) -> GenomeVector:
    return _project_genome(row.genome, feature_prefix="core::")


def _full_genome(row: object) -> GenomeVector:
    genome = row.genome
    if genome.feature_version != GENOME_VERSION:
        raise RuntimeError(
            "GENOME-ADV-001 requires the merged GENOME-NN-001 full representation"
        )
    return genome


def _build_index(rows: list[object], representation: str) -> HistoricalGenomeIndex:
    if representation == "probability":
        vector_fn = _probability_genome
    elif representation == "core":
        vector_fn = _core_genome
    elif representation == "full":
        vector_fn = _full_genome
    else:
        raise ValueError(f"unknown neighborhood representation: {representation!r}")
    return HistoricalGenomeIndex(
        [
            ResidualRecord(
                genome=vector_fn(row),
                residual_favorite=row.core_residual_favorite,
            )
            for row in rows
        ]
    )


def _target_vectors(rows: list[object], representation: str) -> list[GenomeVector]:
    if representation == "probability":
        return [_probability_genome(row) for row in rows]
    if representation == "core":
        return [_core_genome(row) for row in rows]
    if representation == "full":
        return [_full_genome(row) for row in rows]
    raise ValueError(f"unknown neighborhood representation: {representation!r}")


def _build_control_evidence(
    ledger: list[object],
    *,
    min_neighbor_pool: int,
) -> list[_ControlEvidenceRow]:
    years = sorted({row.year for row in ledger})
    result: list[_ControlEvidenceRow] = []

    for test_year in years:
        historical = [row for row in ledger if row.year < test_year]
        targets = [row for row in ledger if row.year == test_year]
        if len(historical) < min_neighbor_pool or not targets:
            continue
        if any(row.year >= test_year for row in historical):
            raise RuntimeError("future/non-historical row entered GENOME-ADV-001 pool")

        indexes = {
            name: _build_index(historical, name)
            for name in ("probability", "core", "full")
        }
        candidate_sets = {
            name: indexes[name].query_candidates(
                _target_vectors(targets, name),
                candidate_limit=_CANDIDATE_LIMIT,
            )
            for name in indexes
        }

        for target_index, row in enumerate(targets):
            summaries = {}
            for name in ("probability", "core", "full"):
                target_vector = _target_vectors([row], name)[0]
                summary = indexes[name].summarize(
                    target_vector,
                    candidate_sets[name][target_index],
                    k=_PRIMARY_K,
                )
                if summary is None:
                    raise RuntimeError(
                        f"registered k={_PRIMARY_K} unavailable for {name} representation"
                    )
                summaries[name] = summary

            result.append(
                _ControlEvidenceRow(
                    match_id=row.match_id,
                    year=row.year,
                    outcome_a=row.outcome_a,
                    outcome_favorite=row.outcome_favorite,
                    orientation_sign=row.genome.orientation_sign,
                    core_probability_a=row.core_probability_a,
                    core_probability_favorite=row.core_probability_favorite,
                    core_residual_favorite=row.core_residual_favorite,
                    probability_neighbor_residual=summaries["probability"].mean_residual,
                    core_neighbor_residual=summaries["core"].mean_residual,
                    full_neighbor_residual=summaries["full"].mean_residual,
                )
            )
    return result


def _fit_meta_model(
    train: list[_ControlEvidenceRow],
    *,
    signal_field: str | None,
):
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000),
    )
    if signal_field is None:
        x_train = [
            [_logit_probability(row.core_probability_favorite)] for row in train
        ]
    else:
        x_train = [
            [
                _logit_probability(row.core_probability_favorite),
                float(getattr(row, signal_field)),
            ]
            for row in train
        ]
    model.fit(x_train, [int(row.outcome_favorite) for row in train])
    return model


def _predict_meta_model(
    model: object,
    test: list[_ControlEvidenceRow],
    *,
    signal_field: str | None,
) -> list[float]:
    if signal_field is None:
        matrix = [[_logit_probability(row.core_probability_favorite)] for row in test]
    else:
        matrix = [
            [
                _logit_probability(row.core_probability_favorite),
                float(getattr(row, signal_field)),
            ]
            for row in test
        ]
    return model.predict_proba(matrix)[:, 1].tolist()


def _score(rows: list[_MetaPredictionRow], probability_field: str) -> ModelScore:
    if not rows:
        raise ValueError("cannot score an empty GENOME-ADV-001 population")
    y_true = [row.outcome_a for row in rows]
    probabilities = [float(getattr(row, probability_field)) for row in rows]
    return ModelScore(
        n=len(rows),
        brier=brier_score(y_true, probabilities),
        log_loss=binary_log_loss(y_true, probabilities),
        accuracy=accuracy(y_true, probabilities),
        ece_10=expected_calibration_error(y_true, probabilities, n_bins=10),
    )


def _comparison(rows: list[_MetaPredictionRow]) -> FourModelComparison:
    control = _score(rows, "calibration_control_probability_a")
    probability = _score(rows, "probability_neighborhood_probability_a")
    core = _score(rows, "core_neighborhood_probability_a")
    full = _score(rows, "full_genome_probability_a")
    return FourModelComparison(
        n=len(rows),
        calibration_control=control,
        probability_neighborhood=probability,
        core_neighborhood=core,
        full_genome=full,
        full_vs_probability_brier_improvement=probability.brier - full.brier,
        full_vs_probability_log_loss_improvement=(
            probability.log_loss - full.log_loss
        ),
        full_vs_core_brier_improvement=core.brier - full.brier,
        full_vs_core_log_loss_improvement=core.log_loss - full.log_loss,
    )


def _meta_predictions(
    evidence: list[_ControlEvidenceRow],
    *,
    min_meta_train_rows: int,
) -> tuple[list[_MetaPredictionRow], tuple[YearComparison, ...]]:
    years = sorted({row.year for row in evidence})
    predictions: list[_MetaPredictionRow] = []
    yearly: list[YearComparison] = []

    for test_year in years:
        train = [row for row in evidence if row.year < test_year]
        test = [row for row in evidence if row.year == test_year]
        if len(train) < min_meta_train_rows or not test:
            continue
        if len({row.outcome_favorite for row in train}) < 2:
            continue

        models = {
            "control": _fit_meta_model(train, signal_field=None),
            "probability": _fit_meta_model(
                train, signal_field="probability_neighbor_residual"
            ),
            "core": _fit_meta_model(train, signal_field="core_neighbor_residual"),
            "full": _fit_meta_model(train, signal_field="full_neighbor_residual"),
        }
        favorite_predictions = {
            "control": _predict_meta_model(models["control"], test, signal_field=None),
            "probability": _predict_meta_model(
                models["probability"],
                test,
                signal_field="probability_neighbor_residual",
            ),
            "core": _predict_meta_model(
                models["core"], test, signal_field="core_neighbor_residual"
            ),
            "full": _predict_meta_model(
                models["full"], test, signal_field="full_neighbor_residual"
            ),
        }

        year_rows: list[_MetaPredictionRow] = []
        for index, row in enumerate(test):
            year_rows.append(
                _MetaPredictionRow(
                    match_id=row.match_id,
                    year=row.year,
                    outcome_a=row.outcome_a,
                    core_probability_a=row.core_probability_a,
                    calibration_control_probability_a=original_probability(
                        favorite_predictions["control"][index],
                        orientation_sign=row.orientation_sign,
                    ),
                    probability_neighborhood_probability_a=original_probability(
                        favorite_predictions["probability"][index],
                        orientation_sign=row.orientation_sign,
                    ),
                    core_neighborhood_probability_a=original_probability(
                        favorite_predictions["core"][index],
                        orientation_sign=row.orientation_sign,
                    ),
                    full_genome_probability_a=original_probability(
                        favorite_predictions["full"][index],
                        orientation_sign=row.orientation_sign,
                    ),
                )
            )
        comparison = _comparison(year_rows)
        yearly.append(
            YearComparison(
                year=test_year,
                comparison=comparison,
                full_joint_win_vs_probability=(
                    comparison.full_genome.brier
                    < comparison.probability_neighborhood.brier
                    and comparison.full_genome.log_loss
                    < comparison.probability_neighborhood.log_loss
                ),
                full_joint_win_vs_core=(
                    comparison.full_genome.brier
                    < comparison.core_neighborhood.brier
                    and comparison.full_genome.log_loss
                    < comparison.core_neighborhood.log_loss
                ),
            )
        )
        predictions.extend(year_rows)
    return predictions, tuple(yearly)


def _equal_count_quintiles(
    rows: list[_ControlEvidenceRow],
    *,
    signal_field: str,
) -> list[list[_ControlEvidenceRow]]:
    ordered = sorted(
        rows,
        key=lambda row: (float(getattr(row, signal_field)), row.match_id),
    )
    buckets: list[list[_ControlEvidenceRow]] = [[] for _ in range(5)]
    total = len(ordered)
    for rank, row in enumerate(ordered):
        buckets[min((rank * 5) // total, 4)].append(row)
    return buckets


def _signal_diagnostic(
    rows: list[_ControlEvidenceRow],
    *,
    signal_field: str,
) -> SignalDiagnostic:
    if not rows:
        return SignalDiagnostic(
            n=0,
            residual_slope_on_signal=None,
            top_minus_bottom_core_residual=None,
            quintiles=(),
        )
    quintiles: list[SignalQuintile] = []
    for index, bucket in enumerate(
        _equal_count_quintiles(rows, signal_field=signal_field),
        start=1,
    ):
        if not bucket:
            continue
        quintiles.append(
            SignalQuintile(
                quintile=index,
                n=len(bucket),
                mean_signal=(
                    sum(float(getattr(row, signal_field)) for row in bucket)
                    / len(bucket)
                ),
                mean_realized_core_residual=(
                    sum(row.core_residual_favorite for row in bucket) / len(bucket)
                ),
            )
        )
    spread = None
    if len(quintiles) >= 2:
        spread = (
            quintiles[-1].mean_realized_core_residual
            - quintiles[0].mean_realized_core_residual
        )
    return SignalDiagnostic(
        n=len(rows),
        residual_slope_on_signal=_linear_slope(
            [float(getattr(row, signal_field)) for row in rows],
            [row.core_residual_favorite for row in rows],
        ),
        top_minus_bottom_core_residual=spread,
        quintiles=tuple(quintiles),
    )


def _recent_evidence(rows: list[_ControlEvidenceRow]) -> list[_ControlEvidenceRow]:
    return [
        row
        for row in rows
        if _RECENT_START_YEAR <= row.year <= _RECENT_END_YEAR
    ]


def _recent_predictions(rows: list[_MetaPredictionRow]) -> list[_MetaPredictionRow]:
    return [
        row
        for row in rows
        if _RECENT_START_YEAR <= row.year <= _RECENT_END_YEAR
    ]


def _gate(
    comparison: FourModelComparison,
    recent_comparison: FourModelComparison | None,
    yearly: tuple[YearComparison, ...],
    *,
    comparator: str,
) -> GateResult:
    if comparator == "probability":
        brier_better = comparison.full_vs_probability_brier_improvement > 0.0
        log_loss_better = comparison.full_vs_probability_log_loss_improvement > 0.0
        joint_wins = sum(item.full_joint_win_vs_probability for item in yearly)
        if recent_comparison is None:
            recent_brier = None
            recent_log_loss = None
        else:
            recent_brier = (
                recent_comparison.full_genome.brier
                <= recent_comparison.probability_neighborhood.brier
            )
            recent_log_loss = (
                recent_comparison.full_genome.log_loss
                <= recent_comparison.probability_neighborhood.log_loss
            )
    elif comparator == "core":
        brier_better = comparison.full_vs_core_brier_improvement > 0.0
        log_loss_better = comparison.full_vs_core_log_loss_improvement > 0.0
        joint_wins = sum(item.full_joint_win_vs_core for item in yearly)
        if recent_comparison is None:
            recent_brier = None
            recent_log_loss = None
        else:
            recent_brier = (
                recent_comparison.full_genome.brier
                <= recent_comparison.core_neighborhood.brier
            )
            recent_log_loss = (
                recent_comparison.full_genome.log_loss
                <= recent_comparison.core_neighborhood.log_loss
            )
    else:
        raise ValueError(f"unknown comparator: {comparator!r}")

    win_rate = joint_wins / len(yearly) if yearly else 0.0
    passed = bool(
        brier_better
        and log_loss_better
        and win_rate >= 0.60
        and recent_brier is True
        and recent_log_loss is True
    )
    return GateResult(
        aggregate_brier_better=brier_better,
        aggregate_log_loss_better=log_loss_better,
        joint_year_win_count=joint_wins,
        evaluated_year_count=len(yearly),
        joint_year_win_rate=win_rate,
        at_least_60_percent_joint_year_wins=win_rate >= 0.60,
        recent_brier_not_worse=recent_brier,
        recent_log_loss_not_worse=recent_log_loss,
        passed=passed,
    )


def _interpretation(gate_a: GateResult, gate_b: GateResult) -> str:
    if not gate_a.passed:
        return "local_core_probability_residual_correction_not_isolated_from_calibration"
    if not gate_b.passed:
        return "core_geometry_local_residual_correction"
    return "structured_matchup_historical_alignment_beyond_local_core_correction"


def run_genome_adversarial_controls(
    matches: list[HistoricalMatch],
    *,
    tour: Tour,
    min_core_train_matches: int = 1000,
    min_neighbor_pool: int = 1000,
    min_meta_train_rows: int = 1000,
    exclude_retirements: bool = True,
) -> GenomeAdversarialReport:
    """Run preregistered GENOME-ADV-001 on matched chronological populations."""
    for name, value in (
        ("min_core_train_matches", min_core_train_matches),
        ("min_neighbor_pool", min_neighbor_pool),
        ("min_meta_train_rows", min_meta_train_rows),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive")

    eligible = _eligible_matches(
        matches,
        tour=tour,
        exclude_retirements=exclude_retirements,
    )
    ledger = _build_core_ledger(
        eligible,
        tour=tour,
        min_core_train_matches=min_core_train_matches,
    )
    if any(row.genome.feature_version != GENOME_VERSION for row in ledger):
        raise RuntimeError("full Genome representation changed from merged GENOME-NN-001")

    evidence = _build_control_evidence(
        ledger,
        min_neighbor_pool=min_neighbor_pool,
    )
    if not evidence:
        raise ValueError("no GENOME-ADV-001 historical neighborhood rows are available")

    predictions, yearly = _meta_predictions(
        evidence,
        min_meta_train_rows=min_meta_train_rows,
    )
    if not predictions:
        raise ValueError("no GENOME-ADV-001 chronological meta-predictions are available")

    comparison = _comparison(predictions)
    recent_predictions = _recent_predictions(predictions)
    recent_comparison = (
        _comparison(recent_predictions) if recent_predictions else None
    )
    recent_evidence = _recent_evidence(evidence)

    gate_a = _gate(
        comparison,
        recent_comparison,
        yearly,
        comparator="probability",
    )
    gate_b = _gate(
        comparison,
        recent_comparison,
        yearly,
        comparator="core",
    )

    evidence_by_id = {row.match_id: row for row in evidence}
    output_predictions = tuple(
        PredictionRow(
            match_id=row.match_id,
            year=row.year,
            outcome_a=row.outcome_a,
            core_probability_a=row.core_probability_a,
            calibration_control_probability_a=row.calibration_control_probability_a,
            probability_neighborhood_probability_a=(
                row.probability_neighborhood_probability_a
            ),
            core_neighborhood_probability_a=row.core_neighborhood_probability_a,
            full_genome_probability_a=row.full_genome_probability_a,
            probability_neighbor_residual=(
                evidence_by_id[row.match_id].probability_neighbor_residual
            ),
            core_neighbor_residual=evidence_by_id[row.match_id].core_neighbor_residual,
            full_neighbor_residual=evidence_by_id[row.match_id].full_neighbor_residual,
        )
        for row in predictions
    )

    return GenomeAdversarialReport(
        experiment_id="GENOME-ADV-001",
        tour=tour,
        development_end_year=_DEVELOPMENT_END_YEAR,
        genome_version=GENOME_VERSION,
        primary_k=_PRIMARY_K,
        candidate_limit=_CANDIDATE_LIMIT,
        min_core_train_matches=min_core_train_matches,
        min_neighbor_pool=min_neighbor_pool,
        min_meta_train_rows=min_meta_train_rows,
        neighbor_population_n=len(evidence),
        meta_population_n=len(predictions),
        comparison=comparison,
        recent_comparison=recent_comparison,
        yearly=yearly,
        probability_signal=_signal_diagnostic(
            evidence,
            signal_field="probability_neighbor_residual",
        ),
        core_signal=_signal_diagnostic(
            evidence,
            signal_field="core_neighbor_residual",
        ),
        full_genome_signal=_signal_diagnostic(
            evidence,
            signal_field="full_neighbor_residual",
        ),
        recent_probability_signal=(
            _signal_diagnostic(
                recent_evidence,
                signal_field="probability_neighbor_residual",
            )
            if recent_evidence
            else None
        ),
        recent_core_signal=(
            _signal_diagnostic(
                recent_evidence,
                signal_field="core_neighbor_residual",
            )
            if recent_evidence
            else None
        ),
        recent_full_genome_signal=(
            _signal_diagnostic(
                recent_evidence,
                signal_field="full_neighbor_residual",
            )
            if recent_evidence
            else None
        ),
        promotion_diagnostics=PromotionDiagnostics(
            gate_a_full_vs_probability=gate_a,
            gate_b_full_vs_core=gate_b,
            interpretation_class=_interpretation(gate_a, gate_b),
        ),
        predictions=output_predictions,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run GENOME-ADV-001 on frozen 2000-2025 development data"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--tour", required=True, choices=("ATP", "WTA"))
    parser.add_argument("--min-core-train-matches", type=int, default=1000)
    parser.add_argument("--min-neighbor-pool", type=int, default=1000)
    parser.add_argument("--min-meta-train-rows", type=int, default=1000)
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
    report = run_genome_adversarial_controls(
        matches,
        tour=args.tour,
        min_core_train_matches=args.min_core_train_matches,
        min_neighbor_pool=args.min_neighbor_pool,
        min_meta_train_rows=args.min_meta_train_rows,
        exclude_retirements=not args.include_retirements,
    )
    print(json.dumps(asdict(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
