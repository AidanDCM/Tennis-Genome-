from __future__ import annotations

import math
import random
from datetime import date, timedelta

from pydantic import field_validator, model_validator

from tennis_genome.data.canonical import (
    HistoricalMatch,
    MatchOutcome,
    MatchStats,
    PreMatchState,
)
from tennis_genome.ratings.dynamic_serve_return import (
    DynamicServeReturnConfig,
    walk_forward_dynamic_serve_return,
)
from tennis_genome.ratings.serve_return import (
    ServeReturnConfig,
    walk_forward_serve_return,
)

from .contracts import WorkbenchRecord


class DynamicStateShiftSpec(WorkbenchRecord):
    """Known-truth state-shift benchmark for serve/return estimators."""

    campaign_id: str
    seeds: tuple[int, ...]
    pre_matches: int = 30
    layoff_days: int = 60
    post_matches: int = 30
    service_points_per_match: int = 60

    base_service_win_rate: float = 0.62
    pre_shift_service_probability: float = 0.72
    post_shift_service_probability: float = 0.55
    opponent_service_probability: float = 0.62

    fixed_learning_rate: float = 0.50
    fixed_reference_points: float = 60.0

    dynamic_initial_variance: float = 0.50
    dynamic_process_variance_per_day: float = 0.001
    dynamic_mean_reversion_half_life_days: float = 365.0
    dynamic_point_information_weight: float = 0.10
    dynamic_min_variance: float = 0.02
    dynamic_max_variance: float = 1.50

    @field_validator("campaign_id")
    @classmethod
    def _campaign_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("campaign_id must be nonblank")
        return value

    @field_validator("seeds")
    @classmethod
    def _seed_family(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if len(value) < 5:
            raise ValueError("dynamic-state benchmark requires at least five seeds")
        if len(value) != len(set(value)):
            raise ValueError("dynamic-state benchmark seeds must be unique")
        return value

    @model_validator(mode="after")
    def _validate_world(self) -> DynamicStateShiftSpec:
        if self.pre_matches < 5 or self.post_matches < 5:
            raise ValueError("dynamic-state benchmark requires at least five matches per phase")
        if self.layoff_days < 0:
            raise ValueError("layoff_days must be non-negative")
        if self.service_points_per_match < 20:
            raise ValueError("service_points_per_match must be at least 20")
        for label, value in (
            ("base_service_win_rate", self.base_service_win_rate),
            ("pre_shift_service_probability", self.pre_shift_service_probability),
            ("post_shift_service_probability", self.post_shift_service_probability),
            ("opponent_service_probability", self.opponent_service_probability),
        ):
            if not 0.0 < value < 1.0:
                raise ValueError(f"{label} must be in (0, 1)")
        return self

    def fixed_config(self) -> ServeReturnConfig:
        return ServeReturnConfig(
            base_service_win_rate=self.base_service_win_rate,
            learning_rate=self.fixed_learning_rate,
            reference_points=self.fixed_reference_points,
        )

    def dynamic_config(self) -> DynamicServeReturnConfig:
        return DynamicServeReturnConfig(
            base_service_win_rate=self.base_service_win_rate,
            initial_variance=self.dynamic_initial_variance,
            process_variance_per_day=self.dynamic_process_variance_per_day,
            mean_reversion_half_life_days=self.dynamic_mean_reversion_half_life_days,
            point_information_weight=self.dynamic_point_information_weight,
            min_variance=self.dynamic_min_variance,
            max_variance=self.dynamic_max_variance,
        )


class DynamicStateSeedResult(WorkbenchRecord):
    seed: int
    fixed_mse_to_true_probability: float
    dynamic_mse_to_true_probability: float
    fixed_expected_log_loss: float
    dynamic_expected_log_loss: float
    mse_improvement: float
    expected_log_loss_improvement: float
    dynamic_wins_both: bool


class DynamicStateShiftReport(WorkbenchRecord):
    campaign_spec_sha256: str
    campaign_id: str
    n_seeds: int
    dynamic_joint_win_count: int
    dynamic_joint_win_rate: float
    mean_fixed_mse: float
    mean_dynamic_mse: float
    mean_fixed_expected_log_loss: float
    mean_dynamic_expected_log_loss: float
    results: tuple[DynamicStateSeedResult, ...]


def _binomial(rng: random.Random, n: int, probability: float) -> int:
    return sum(rng.random() < probability for _ in range(n))


def _synthetic_match(
    *,
    match_id: str,
    event_date: date,
    opponent_id: str,
    a_service_won: int,
    b_service_won: int,
    service_points: int,
) -> HistoricalMatch:
    return HistoricalMatch(
        pre_match=PreMatchState(
            match_id=match_id,
            tour="ATP",
            event_date=event_date,
            source_order=0,
            tournament_id="synthetic-state-shift",
            tournament_name="Synthetic State Shift",
            tournament_level="A",
            surface="Hard",
            round="R32",
            best_of=3,
            player_a_id="FOCAL",
            player_b_id=opponent_id,
            player_a_name="Focal",
            player_b_name=opponent_id,
            rank_a=None,
            rank_b=None,
            rank_points_a=None,
            rank_points_b=None,
        ),
        outcome=MatchOutcome(
            match_id=match_id,
            a_won=a_service_won >= b_service_won,
            score="synthetic",
            retirement=False,
            walkover=False,
        ),
        stats=MatchStats(
            match_id=match_id,
            service_points_a=service_points,
            service_points_b=service_points,
            first_serve_points_won_a=a_service_won,
            first_serve_points_won_b=b_service_won,
            second_serve_points_won_a=0,
            second_serve_points_won_b=0,
        ),
    )


def _build_world(
    spec: DynamicStateShiftSpec,
    *,
    seed: int,
) -> tuple[list[HistoricalMatch], dict[str, float]]:
    rng = random.Random(seed)
    event_date = date(2024, 1, 1)
    matches: list[HistoricalMatch] = []
    post_truth: dict[str, float] = {}

    phases = (
        ("pre", spec.pre_matches, spec.pre_shift_service_probability),
        ("post", spec.post_matches, spec.post_shift_service_probability),
    )
    for phase, count, focal_service_probability in phases:
        if phase == "post":
            event_date += timedelta(days=spec.layoff_days)

        for index in range(count):
            match_id = f"shift-{seed}-{phase}-{index:03d}"
            opponent_id = f"OPP-{seed}-{phase}-{index:03d}"
            a_won = _binomial(
                rng,
                spec.service_points_per_match,
                focal_service_probability,
            )
            b_won = _binomial(
                rng,
                spec.service_points_per_match,
                spec.opponent_service_probability,
            )
            matches.append(
                _synthetic_match(
                    match_id=match_id,
                    event_date=event_date,
                    opponent_id=opponent_id,
                    a_service_won=a_won,
                    b_service_won=b_won,
                    service_points=spec.service_points_per_match,
                )
            )
            if phase == "post":
                post_truth[match_id] = focal_service_probability
            event_date += timedelta(days=1)

    return matches, post_truth


def _expected_log_loss(true_probability: float, predicted_probability: float) -> float:
    clipped = min(max(predicted_probability, 1e-12), 1.0 - 1e-12)
    return -(
        true_probability * math.log(clipped)
        + (1.0 - true_probability) * math.log(1.0 - clipped)
    )


def _mean(values: list[float]) -> float:
    if not values:
        raise ValueError("cannot average an empty collection")
    return sum(values) / len(values)


def run_dynamic_state_shift_benchmark(
    spec: DynamicStateShiftSpec,
) -> DynamicStateShiftReport:
    """Compare fixed and uncertainty-aware state against known post-shift truth.

    The benchmark scores the estimators' pre-match service-point probabilities against
    the planted true service probability after the layoff/state change. It is an
    estimator diagnostic, not a match-win forecasting evaluation.
    """

    results: list[DynamicStateSeedResult] = []
    for seed in spec.seeds:
        matches, truth = _build_world(spec, seed=seed)
        fixed = {
            snapshot.match_id: snapshot
            for snapshot in walk_forward_serve_return(
                matches,
                config=spec.fixed_config(),
            )
        }
        dynamic = {
            snapshot.match_id: snapshot
            for snapshot in walk_forward_dynamic_serve_return(
                matches,
                config=spec.dynamic_config(),
            )
        }

        fixed_squared: list[float] = []
        dynamic_squared: list[float] = []
        fixed_log: list[float] = []
        dynamic_log: list[float] = []
        for match_id, true_probability in truth.items():
            fixed_probability = fixed[match_id].probability_a_serve_point
            dynamic_probability = dynamic[match_id].probability_a_serve_point
            fixed_squared.append((fixed_probability - true_probability) ** 2)
            dynamic_squared.append((dynamic_probability - true_probability) ** 2)
            fixed_log.append(
                _expected_log_loss(true_probability, fixed_probability)
            )
            dynamic_log.append(
                _expected_log_loss(true_probability, dynamic_probability)
            )

        fixed_mse = _mean(fixed_squared)
        dynamic_mse = _mean(dynamic_squared)
        fixed_expected_log = _mean(fixed_log)
        dynamic_expected_log = _mean(dynamic_log)
        mse_improvement = fixed_mse - dynamic_mse
        log_improvement = fixed_expected_log - dynamic_expected_log
        results.append(
            DynamicStateSeedResult(
                seed=seed,
                fixed_mse_to_true_probability=fixed_mse,
                dynamic_mse_to_true_probability=dynamic_mse,
                fixed_expected_log_loss=fixed_expected_log,
                dynamic_expected_log_loss=dynamic_expected_log,
                mse_improvement=mse_improvement,
                expected_log_loss_improvement=log_improvement,
                dynamic_wins_both=mse_improvement > 0.0 and log_improvement > 0.0,
            )
        )

    wins = sum(result.dynamic_wins_both for result in results)
    return DynamicStateShiftReport(
        campaign_spec_sha256=spec.semantic_sha256,
        campaign_id=spec.campaign_id,
        n_seeds=len(results),
        dynamic_joint_win_count=wins,
        dynamic_joint_win_rate=wins / len(results),
        mean_fixed_mse=_mean(
            [result.fixed_mse_to_true_probability for result in results]
        ),
        mean_dynamic_mse=_mean(
            [result.dynamic_mse_to_true_probability for result in results]
        ),
        mean_fixed_expected_log_loss=_mean(
            [result.fixed_expected_log_loss for result in results]
        ),
        mean_dynamic_expected_log_loss=_mean(
            [result.dynamic_expected_log_loss for result in results]
        ),
        results=tuple(results),
    )
