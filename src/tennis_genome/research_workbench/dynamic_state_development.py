from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from pydantic import field_validator, model_validator

from tennis_genome.data.canonical import HistoricalMatch, Tour
from tennis_genome.evaluation.block_inference import (
    PairedBlockBootstrapResult,
    PairedBlockPermutationResult,
    paired_block_bootstrap_improvement,
    paired_block_sign_flip_test,
)
from tennis_genome.evaluation.metrics import binary_log_loss, brier_score
from tennis_genome.evaluation.walkforward import walk_forward_elo
from tennis_genome.models.feature_probability import FeatureProbabilityModel
from tennis_genome.ratings.dynamic_serve_return import (
    DynamicServeReturnConfig,
    walk_forward_dynamic_serve_return,
)
from tennis_genome.ratings.serve_return import (
    ServeReturnConfig,
    walk_forward_serve_return,
)

from .contracts import WorkbenchRecord


@dataclass(frozen=True)
class _StateSnapshot:
    match_id: str
    event_date_year: int
    event_date_iso: str
    elo_logit: float
    serve_return_edge: float


class DynamicStateDevelopmentSpec(WorkbenchRecord):
    """Registered development comparison for fixed versus dynamic serve/return state."""

    experiment_id: str = "DYNAMIC-STATE-DEVELOPMENT-001"
    tour: Tour
    test_years: tuple[int, ...] = tuple(range(2015, 2026))
    min_train_rows: int = 5_000
    exclude_retirements: bool = True

    fixed_base_service_win_rate: float = 0.62
    fixed_learning_rate: float = 0.50
    fixed_reference_points: float = 60.0

    dynamic_base_service_win_rate: float = 0.62
    dynamic_initial_variance: float = 0.50
    dynamic_process_variance_per_day: float = 0.001
    dynamic_mean_reversion_half_life_days: float = 365.0
    dynamic_point_information_weight: float = 0.10
    dynamic_min_variance: float = 0.02
    dynamic_max_variance: float = 1.50

    block_definition: Literal["ISO_CALENDAR_WEEK"] = "ISO_CALENDAR_WEEK"
    confidence_level: float = 0.95
    bootstrap_resamples: int = 10_000
    permutation_resamples: int = 20_000
    inference_seed: int = 20260914

    @field_validator("experiment_id")
    @classmethod
    def _nonblank_experiment(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("experiment_id must be nonblank")
        return value

    @field_validator("test_years")
    @classmethod
    def _years(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if not value:
            raise ValueError("test_years must be non-empty")
        if len(set(value)) != len(value) or tuple(sorted(value)) != value:
            raise ValueError("test_years must be unique and sorted")
        return value

    @model_validator(mode="after")
    def _validate_spec(self) -> DynamicStateDevelopmentSpec:
        if self.min_train_rows <= 0:
            raise ValueError("min_train_rows must be positive")
        if not 0.0 < self.confidence_level < 1.0:
            raise ValueError("confidence_level must be in (0, 1)")
        if self.bootstrap_resamples <= 0 or self.permutation_resamples <= 0:
            raise ValueError("inference resample counts must be positive")
        return self

    def fixed_config(self) -> ServeReturnConfig:
        return ServeReturnConfig(
            base_service_win_rate=self.fixed_base_service_win_rate,
            learning_rate=self.fixed_learning_rate,
            reference_points=self.fixed_reference_points,
        )

    def dynamic_config(self) -> DynamicServeReturnConfig:
        return DynamicServeReturnConfig(
            base_service_win_rate=self.dynamic_base_service_win_rate,
            initial_variance=self.dynamic_initial_variance,
            process_variance_per_day=self.dynamic_process_variance_per_day,
            mean_reversion_half_life_days=self.dynamic_mean_reversion_half_life_days,
            point_information_weight=self.dynamic_point_information_weight,
            min_variance=self.dynamic_min_variance,
            max_variance=self.dynamic_max_variance,
        )


class DynamicStatePredictionRow(WorkbenchRecord):
    match_id: str
    event_date: str
    test_year: int
    block_id: str
    outcome_a: bool
    fixed_probability_a: float
    dynamic_probability_a: float
    fixed_brier_loss: float
    dynamic_brier_loss: float
    fixed_log_loss: float
    dynamic_log_loss: float


class DynamicStateYearScore(WorkbenchRecord):
    year: int
    n: int
    fixed_brier: float
    dynamic_brier: float
    brier_improvement: float
    fixed_log_loss: float
    dynamic_log_loss: float
    log_loss_improvement: float


class DynamicStateDevelopmentReport(WorkbenchRecord):
    experiment_id: str
    experiment_spec_sha256: str
    tour: Tour
    feature_names: tuple[str, ...]
    evaluated_years: tuple[int, ...]
    training_rule: str
    block_definition: str
    n_predictions: int
    year_scores: tuple[DynamicStateYearScore, ...]
    overall_fixed_brier: float
    overall_dynamic_brier: float
    overall_brier_improvement: float
    overall_fixed_log_loss: float
    overall_dynamic_log_loss: float
    overall_log_loss_improvement: float
    brier_bootstrap: dict[str, float | int]
    log_loss_bootstrap: dict[str, float | int]
    brier_sign_flip: dict[str, float | int | bool | None]
    log_loss_sign_flip: dict[str, float | int | bool | None]
    predictions: tuple[DynamicStatePredictionRow, ...]
    evidence_role: Literal["DEVELOPMENT_ONLY"] = "DEVELOPMENT_ONLY"


def _logit(probability: float) -> float:
    clipped = min(max(float(probability), 1e-9), 1.0 - 1e-9)
    return math.log(clipped / (1.0 - clipped))


def _single_log_loss(outcome: bool, probability: float) -> float:
    p = min(max(float(probability), 1e-12), 1.0 - 1e-12)
    return -(math.log(p) if outcome else math.log(1.0 - p))


def _single_brier(outcome: bool, probability: float) -> float:
    return (float(probability) - float(outcome)) ** 2


def _block_id(event_date_iso: str) -> str:
    from datetime import date

    parsed = date.fromisoformat(event_date_iso)
    iso = parsed.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _bootstrap_dict(result: PairedBlockBootstrapResult) -> dict[str, float | int]:
    return {
        "improvement": result.improvement,
        "lower": result.lower,
        "upper": result.upper,
        "confidence_level": result.confidence_level,
        "n_pairs": result.n_pairs,
        "n_blocks": result.n_blocks,
        "n_resamples": result.n_resamples,
    }


def _permutation_dict(
    result: PairedBlockPermutationResult,
) -> dict[str, float | int | bool | None]:
    return {
        "improvement": result.improvement,
        "p_value": result.p_value,
        "n_pairs": result.n_pairs,
        "n_blocks": result.n_blocks,
        "n_resamples": result.n_resamples,
        "exact": result.exact,
    }


def _eligible_matches(
    matches: list[HistoricalMatch],
    *,
    tour: Tour,
    exclude_retirements: bool,
) -> list[HistoricalMatch]:
    observed_tours = {match.pre_match.tour for match in matches}
    if observed_tours and observed_tours != {tour}:
        raise ValueError(
            f"development comparison requires only {tour} matches; got {sorted(observed_tours)}"
        )
    return [
        match
        for match in matches
        if not match.outcome.walkover
        and (not exclude_retirements or not match.outcome.retirement)
    ]


def _state_snapshots(
    matches: list[HistoricalMatch],
    *,
    fixed_config: ServeReturnConfig,
    dynamic_config: DynamicServeReturnConfig,
) -> tuple[dict[str, _StateSnapshot], dict[str, _StateSnapshot]]:
    elo = {row.match_id: row for row in walk_forward_elo(matches, exclude_retirements=False)}
    fixed = {
        row.match_id: row
        for row in walk_forward_serve_return(
            matches,
            config=fixed_config,
            exclude_retirements=False,
        )
    }
    dynamic = {
        row.match_id: row
        for row in walk_forward_dynamic_serve_return(
            matches,
            config=dynamic_config,
            exclude_retirements=False,
        )
    }
    match_dates = {
        match.match_id: match.pre_match.event_date
        for match in matches
    }
    common = sorted(set(elo) & set(fixed) & set(dynamic))
    baseline: dict[str, _StateSnapshot] = {}
    challenger: dict[str, _StateSnapshot] = {}
    for match_id in common:
        event_date = match_dates[match_id]
        baseline[match_id] = _StateSnapshot(
            match_id=match_id,
            event_date_year=event_date.year,
            event_date_iso=event_date.isoformat(),
            elo_logit=_logit(elo[match_id].probability_a),
            serve_return_edge=float(fixed[match_id].matchup_edge_a),
        )
        challenger[match_id] = _StateSnapshot(
            match_id=match_id,
            event_date_year=event_date.year,
            event_date_iso=event_date.isoformat(),
            elo_logit=_logit(elo[match_id].probability_a),
            serve_return_edge=float(dynamic[match_id].matchup_edge_a),
        )
    return baseline, challenger


def run_dynamic_state_development_comparison(
    matches: list[HistoricalMatch],
    spec: DynamicStateDevelopmentSpec,
) -> DynamicStateDevelopmentReport:
    """Chronological development-only match-win comparison of two state estimators.

    The two procedures are deliberately identical except for the serve/return state:
    both use a logistic mapping from overall Elo logit plus one opponent-adjusted
    serve/return matchup edge. No target ranking, surface, seed, age, or other currently
    unresolved target-row context enters this experiment.

    For every test year Y the predictive mappings are fit only on rows from years < Y.
    State construction remains fully chronological with the repository's conservative
    same-day freeze. This experiment is development evidence and cannot establish
    protected or prospective superiority.
    """

    eligible = _eligible_matches(
        matches,
        tour=spec.tour,
        exclude_retirements=spec.exclude_retirements,
    )
    if not eligible:
        raise ValueError("no eligible matches for dynamic-state development comparison")

    fixed_snapshots, dynamic_snapshots = _state_snapshots(
        eligible,
        fixed_config=spec.fixed_config(),
        dynamic_config=spec.dynamic_config(),
    )
    outcomes = {match.match_id: match.outcome.a_won for match in eligible}
    features = ("elo_logit", "serve_return_edge")

    predictions: list[DynamicStatePredictionRow] = []
    year_scores: list[DynamicStateYearScore] = []

    for year in spec.test_years:
        train_ids = [
            match_id
            for match_id, snapshot in fixed_snapshots.items()
            if snapshot.event_date_year < year and match_id in dynamic_snapshots
        ]
        test_ids = [
            match_id
            for match_id, snapshot in fixed_snapshots.items()
            if snapshot.event_date_year == year and match_id in dynamic_snapshots
        ]
        train_ids.sort(
            key=lambda match_id: (
                fixed_snapshots[match_id].event_date_iso,
                match_id,
            )
        )
        test_ids.sort(
            key=lambda match_id: (
                fixed_snapshots[match_id].event_date_iso,
                match_id,
            )
        )
        if len(train_ids) < spec.min_train_rows or not test_ids:
            continue

        train_outcomes = [outcomes[match_id] for match_id in train_ids]
        if len(set(train_outcomes)) < 2:
            raise ValueError(f"training rows before {year} contain only one outcome class")

        fixed_model = FeatureProbabilityModel(features).fit(
            [fixed_snapshots[match_id] for match_id in train_ids],
            train_outcomes,
        )
        dynamic_model = FeatureProbabilityModel(features).fit(
            [dynamic_snapshots[match_id] for match_id in train_ids],
            train_outcomes,
        )
        fixed_probabilities = fixed_model.predict_probabilities(
            [fixed_snapshots[match_id] for match_id in test_ids]
        )
        dynamic_probabilities = dynamic_model.predict_probabilities(
            [dynamic_snapshots[match_id] for match_id in test_ids]
        )
        year_outcomes = [outcomes[match_id] for match_id in test_ids]

        fixed_brier = brier_score(year_outcomes, fixed_probabilities)
        dynamic_brier = brier_score(year_outcomes, dynamic_probabilities)
        fixed_log = binary_log_loss(year_outcomes, fixed_probabilities)
        dynamic_log = binary_log_loss(year_outcomes, dynamic_probabilities)
        year_scores.append(
            DynamicStateYearScore(
                year=year,
                n=len(test_ids),
                fixed_brier=fixed_brier,
                dynamic_brier=dynamic_brier,
                brier_improvement=fixed_brier - dynamic_brier,
                fixed_log_loss=fixed_log,
                dynamic_log_loss=dynamic_log,
                log_loss_improvement=fixed_log - dynamic_log,
            )
        )

        for match_id, fixed_p, dynamic_p in zip(
            test_ids,
            fixed_probabilities,
            dynamic_probabilities,
            strict=True,
        ):
            outcome = outcomes[match_id]
            event_date = fixed_snapshots[match_id].event_date_iso
            predictions.append(
                DynamicStatePredictionRow(
                    match_id=match_id,
                    event_date=event_date,
                    test_year=year,
                    block_id=_block_id(event_date),
                    outcome_a=outcome,
                    fixed_probability_a=fixed_p,
                    dynamic_probability_a=dynamic_p,
                    fixed_brier_loss=_single_brier(outcome, fixed_p),
                    dynamic_brier_loss=_single_brier(outcome, dynamic_p),
                    fixed_log_loss=_single_log_loss(outcome, fixed_p),
                    dynamic_log_loss=_single_log_loss(outcome, dynamic_p),
                )
            )

    if not predictions:
        raise ValueError(
            "no development years met the registered training-row and test-row requirements"
        )

    outcomes_all = [row.outcome_a for row in predictions]
    fixed_probabilities_all = [row.fixed_probability_a for row in predictions]
    dynamic_probabilities_all = [row.dynamic_probability_a for row in predictions]
    block_ids = [row.block_id for row in predictions]

    brier_bootstrap = paired_block_bootstrap_improvement(
        [row.fixed_brier_loss for row in predictions],
        [row.dynamic_brier_loss for row in predictions],
        block_ids,
        confidence_level=spec.confidence_level,
        n_resamples=spec.bootstrap_resamples,
        seed=spec.inference_seed,
    )
    log_bootstrap = paired_block_bootstrap_improvement(
        [row.fixed_log_loss for row in predictions],
        [row.dynamic_log_loss for row in predictions],
        block_ids,
        confidence_level=spec.confidence_level,
        n_resamples=spec.bootstrap_resamples,
        seed=spec.inference_seed,
    )
    brier_permutation = paired_block_sign_flip_test(
        [row.fixed_brier_loss for row in predictions],
        [row.dynamic_brier_loss for row in predictions],
        block_ids,
        n_resamples=spec.permutation_resamples,
        seed=spec.inference_seed,
    )
    log_permutation = paired_block_sign_flip_test(
        [row.fixed_log_loss for row in predictions],
        [row.dynamic_log_loss for row in predictions],
        block_ids,
        n_resamples=spec.permutation_resamples,
        seed=spec.inference_seed,
    )

    fixed_brier_all = brier_score(outcomes_all, fixed_probabilities_all)
    dynamic_brier_all = brier_score(outcomes_all, dynamic_probabilities_all)
    fixed_log_all = binary_log_loss(outcomes_all, fixed_probabilities_all)
    dynamic_log_all = binary_log_loss(outcomes_all, dynamic_probabilities_all)

    return DynamicStateDevelopmentReport(
        experiment_id=spec.experiment_id,
        experiment_spec_sha256=spec.semantic_sha256,
        tour=spec.tour,
        feature_names=features,
        evaluated_years=tuple(score.year for score in year_scores),
        training_rule="for test year Y, fit each mapping only on rows with year < Y",
        block_definition=spec.block_definition,
        n_predictions=len(predictions),
        year_scores=tuple(year_scores),
        overall_fixed_brier=fixed_brier_all,
        overall_dynamic_brier=dynamic_brier_all,
        overall_brier_improvement=fixed_brier_all - dynamic_brier_all,
        overall_fixed_log_loss=fixed_log_all,
        overall_dynamic_log_loss=dynamic_log_all,
        overall_log_loss_improvement=fixed_log_all - dynamic_log_all,
        brier_bootstrap=_bootstrap_dict(brier_bootstrap),
        log_loss_bootstrap=_bootstrap_dict(log_bootstrap),
        brier_sign_flip=_permutation_dict(brier_permutation),
        log_loss_sign_flip=_permutation_dict(log_permutation),
        predictions=tuple(predictions),
    )
