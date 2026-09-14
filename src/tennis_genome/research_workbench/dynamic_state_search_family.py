from __future__ import annotations

from itertools import product
from typing import Literal, cast

from pydantic import field_validator, model_validator

from tennis_genome.data.canonical import Tour
from tennis_genome.ratings.dynamic_serve_return import DynamicServeReturnConfig

from .contracts import WorkbenchRecord
from .dynamic_state_development import DynamicStateDevelopmentSpec
from .lineage import ProcedureSearchFamily

PrimaryMetric = Literal["BRIER", "LOG_LOSS"]

_PROCESS_VARIANCES = (0.00025, 0.00050)
_HALF_LIVES = (730.0, 1460.0)
_MAX_VARIANCES = (0.75, 1.00)


def _candidate_id(process_variance: float, half_life: float, max_variance: float) -> str:
    process_code = "00025" if process_variance == 0.00025 else "00050"
    max_code = "075" if max_variance == 0.75 else "100"
    return f"DYN-LA-PV{process_code}-HL{int(half_life)}-MV{max_code}"


class LessAggressiveDynamicCandidate(WorkbenchRecord):
    """One frozen member of the less-aggressive dynamic-state search family."""

    candidate_id: str
    process_variance_per_day: float
    mean_reversion_half_life_days: float
    max_variance: float

    @model_validator(mode="after")
    def _validate_candidate(self) -> LessAggressiveDynamicCandidate:
        expected = _candidate_id(
            self.process_variance_per_day,
            self.mean_reversion_half_life_days,
            self.max_variance,
        )
        if self.candidate_id != expected:
            raise ValueError("candidate_id does not match registered parameter values")
        if self.process_variance_per_day not in _PROCESS_VARIANCES:
            raise ValueError("candidate process variance is outside frozen family")
        if self.mean_reversion_half_life_days not in _HALF_LIVES:
            raise ValueError("candidate half-life is outside frozen family")
        if self.max_variance not in _MAX_VARIANCES:
            raise ValueError("candidate variance ceiling is outside frozen family")
        return self

    def dynamic_config(self) -> DynamicServeReturnConfig:
        return DynamicServeReturnConfig(
            base_service_win_rate=0.62,
            initial_variance=0.50,
            process_variance_per_day=self.process_variance_per_day,
            mean_reversion_half_life_days=self.mean_reversion_half_life_days,
            point_information_weight=0.10,
            min_variance=0.02,
            max_variance=self.max_variance,
        )


def registered_less_aggressive_candidates() -> tuple[LessAggressiveDynamicCandidate, ...]:
    candidates = [
        LessAggressiveDynamicCandidate(
            candidate_id=_candidate_id(process_variance, half_life, max_variance),
            process_variance_per_day=process_variance,
            mean_reversion_half_life_days=half_life,
            max_variance=max_variance,
        )
        for process_variance, half_life, max_variance in product(
            _PROCESS_VARIANCES,
            _HALF_LIVES,
            _MAX_VARIANCES,
        )
    ]
    return tuple(sorted(candidates, key=lambda candidate: candidate.candidate_id))


class DynamicStateLessAggressiveFamilySpec(WorkbenchRecord):
    """Preregistered family for a bounded historical dynamic-state parameter search."""

    family_id: str = "DYNAMIC-STATE-LESS-AGGRESSIVE-SEARCH-001"
    parent_experiment_id: str = "DYNAMIC-STATE-DEVELOPMENT-001"
    motivation_diagnostic_id: str = "DYNAMIC-STATE-FAILURE-DIAGNOSTIC-001"
    candidates: tuple[LessAggressiveDynamicCandidate, ...] = (
        registered_less_aggressive_candidates()
    )
    tours: tuple[Tour, ...] = ("ATP", "WTA")
    test_years: tuple[int, ...] = tuple(range(2015, 2026))
    min_train_rows: int = 5_000

    fixed_base_service_win_rate: float = 0.62
    fixed_learning_rate: float = 0.50
    fixed_reference_points: float = 60.0

    dynamic_base_service_win_rate: float = 0.62
    dynamic_initial_variance: float = 0.50
    dynamic_point_information_weight: float = 0.10
    dynamic_min_variance: float = 0.02

    block_definition: Literal["ISO_CALENDAR_WEEK"] = "ISO_CALENDAR_WEEK"
    confidence_level: float = 0.95
    bootstrap_resamples: int = 10_000
    permutation_resamples: int = 20_000
    inference_seed: int = 20260914

    primary_metrics: tuple[PrimaryMetric, ...] = ("BRIER", "LOG_LOSS")
    familywise_alpha: float = 0.05
    selection_rule: Literal[
        "FOUR_CELL_POSITIVE_THEN_POOLED_LOG_LOSS_THEN_BRIER_THEN_ID"
    ] = "FOUR_CELL_POSITIVE_THEN_POOLED_LOG_LOSS_THEN_BRIER_THEN_ID"
    evidence_role: Literal["DEVELOPMENT_SEARCH_ONLY"] = "DEVELOPMENT_SEARCH_ONLY"

    @field_validator("test_years")
    @classmethod
    def _validate_years(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if not value or tuple(sorted(set(value))) != value:
            raise ValueError("test_years must be non-empty, unique and sorted")
        return value

    @model_validator(mode="after")
    def _validate_family(self) -> DynamicStateLessAggressiveFamilySpec:
        expected = registered_less_aggressive_candidates()
        if tuple(candidate.canonical_payload() for candidate in self.candidates) != tuple(
            candidate.canonical_payload() for candidate in expected
        ):
            raise ValueError("candidate set must equal the complete frozen 2x2x2 family")
        if self.tours != ("ATP", "WTA"):
            raise ValueError("search family requires both ATP and WTA")
        if self.min_train_rows <= 0:
            raise ValueError("min_train_rows must be positive")
        if self.primary_metrics != ("BRIER", "LOG_LOSS"):
            raise ValueError("primary metrics are frozen to Brier and log loss")
        if not 0.0 < self.familywise_alpha < 1.0:
            raise ValueError("familywise_alpha must be in (0, 1)")
        if self.bootstrap_resamples <= 0 or self.permutation_resamples <= 0:
            raise ValueError("inference resample counts must be positive")
        return self

    @property
    def primary_claim_count(self) -> int:
        return len(self.candidates) * len(self.tours) * len(self.primary_metrics)

    @property
    def bonferroni_alpha(self) -> float:
        return self.familywise_alpha / self.primary_claim_count

    def search_family(self) -> ProcedureSearchFamily:
        return ProcedureSearchFamily(
            family_id=self.family_id,
            research_question=(
                "Can a fully preregistered less-aggressive dynamic serve/return state "
                "improve both proper scores on both ATP and WTA historical development?"
            ),
            procedure_ids=tuple(candidate.candidate_id for candidate in self.candidates),
            datasets_touched=(
                "DYNAMIC-STATE-DEVELOPMENT-001-ATP",
                "DYNAMIC-STATE-DEVELOPMENT-001-WTA",
            ),
            unregistered_variant_count=0,
            parameter_search_count=0,
            feature_versions=("elo_logit+serve_return_edge-v1",),
            search_method=(
                "Complete frozen 2x2x2 factorial: process variance x mean-reversion "
                "half-life x variance ceiling; all eight candidates evaluated on both "
                "tours before any winner is selected."
            ),
            frozen=True,
        )

    def development_spec(
        self,
        *,
        candidate: LessAggressiveDynamicCandidate,
        tour: Tour,
    ) -> DynamicStateDevelopmentSpec:
        registered = {item.candidate_id: item for item in self.candidates}
        if candidate.candidate_id not in registered:
            raise ValueError("candidate is not registered in frozen search family")
        if tour not in self.tours:
            raise ValueError("tour is not registered in frozen search family")
        exact = registered[candidate.candidate_id]
        return DynamicStateDevelopmentSpec(
            experiment_id=f"{self.family_id}:{exact.candidate_id}:{tour}",
            tour=cast(Tour, tour),
            test_years=self.test_years,
            min_train_rows=self.min_train_rows,
            exclude_retirements=True,
            fixed_base_service_win_rate=self.fixed_base_service_win_rate,
            fixed_learning_rate=self.fixed_learning_rate,
            fixed_reference_points=self.fixed_reference_points,
            dynamic_base_service_win_rate=self.dynamic_base_service_win_rate,
            dynamic_initial_variance=self.dynamic_initial_variance,
            dynamic_process_variance_per_day=exact.process_variance_per_day,
            dynamic_mean_reversion_half_life_days=exact.mean_reversion_half_life_days,
            dynamic_point_information_weight=self.dynamic_point_information_weight,
            dynamic_min_variance=self.dynamic_min_variance,
            dynamic_max_variance=exact.max_variance,
            block_definition=self.block_definition,
            confidence_level=self.confidence_level,
            bootstrap_resamples=self.bootstrap_resamples,
            permutation_resamples=self.permutation_resamples,
            inference_seed=self.inference_seed,
        )
