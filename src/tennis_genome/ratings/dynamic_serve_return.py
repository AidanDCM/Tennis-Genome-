from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from itertools import groupby
from math import exp, isfinite, log, sqrt

from tennis_genome.data.canonical import HistoricalMatch, MatchStats


@dataclass(frozen=True)
class DynamicServeReturnConfig:
    """Configuration for uncertainty-aware dynamic serve/return state research."""

    base_service_win_rate: float = 0.62
    initial_variance: float = 0.50
    process_variance_per_day: float = 0.001
    mean_reversion_half_life_days: float = 365.0
    point_information_weight: float = 0.10
    min_variance: float = 0.02
    max_variance: float = 1.50

    def __post_init__(self) -> None:
        if not 0.0 < self.base_service_win_rate < 1.0:
            raise ValueError("base_service_win_rate must be between zero and one")
        if self.initial_variance <= 0.0:
            raise ValueError("initial_variance must be positive")
        if self.process_variance_per_day < 0.0:
            raise ValueError("process_variance_per_day must be non-negative")
        if self.mean_reversion_half_life_days <= 0.0:
            raise ValueError("mean_reversion_half_life_days must be positive")
        if not 0.0 < self.point_information_weight <= 1.0:
            raise ValueError("point_information_weight must be in (0, 1]")
        if not 0.0 < self.min_variance <= self.initial_variance:
            raise ValueError("min_variance must be positive and no larger than initial_variance")
        if self.max_variance < self.initial_variance:
            raise ValueError("max_variance must be at least initial_variance")


@dataclass(frozen=True)
class DynamicPlayerState:
    """One player's posterior state after the most recent completed source date."""

    serve_mean: float
    serve_variance: float
    return_mean: float
    return_variance: float
    prior_serve_points: int
    prior_return_points: int
    last_update_date: date


@dataclass(frozen=True)
class DynamicServeReturnSnapshot:
    """Uncertainty-aware serve/return state visible before one source date."""

    match_id: str
    event_date: date
    probability_a_serve_point: float
    probability_b_serve_point: float
    matchup_edge_a: float

    serve_mean_a: float
    serve_mean_b: float
    return_mean_a: float
    return_mean_b: float

    serve_sd_a: float
    serve_sd_b: float
    return_sd_a: float
    return_sd_b: float

    a_serve_logit_sd: float
    b_serve_logit_sd: float

    prior_serve_points_a: int
    prior_serve_points_b: int
    prior_return_points_a: int
    prior_return_points_b: int


@dataclass
class _UpdateAccumulator:
    gradient: float = 0.0
    information: float = 0.0
    points: int = 0


def _logit(probability: float) -> float:
    return log(probability / (1.0 - probability))


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        z = exp(-value)
        return 1.0 / (1.0 + z)
    z = exp(value)
    return z / (1.0 + z)


def _service_observation(
    stats: MatchStats,
    *,
    side: str,
) -> tuple[int, int] | None:
    if side == "a":
        total = stats.service_points_a
        won = stats.service_points_won_a
    elif side == "b":
        total = stats.service_points_b
        won = stats.service_points_won_b
    else:
        raise ValueError(f"invalid side: {side!r}")

    if total is None or won is None or total <= 0:
        return None
    if won < 0 or won > total:
        return None
    return won, total


def _eligible(match: HistoricalMatch, *, exclude_retirements: bool) -> bool:
    if match.outcome.walkover:
        return False
    if exclude_retirements and match.outcome.retirement:
        return False
    return True


def _new_state(event_date: date, config: DynamicServeReturnConfig) -> DynamicPlayerState:
    return DynamicPlayerState(
        serve_mean=0.0,
        serve_variance=config.initial_variance,
        return_mean=0.0,
        return_variance=config.initial_variance,
        prior_serve_points=0,
        prior_return_points=0,
        last_update_date=event_date,
    )


def _advance_state(
    state: DynamicPlayerState,
    *,
    event_date: date,
    config: DynamicServeReturnConfig,
) -> DynamicPlayerState:
    days = (event_date - state.last_update_date).days
    if days < 0:
        raise ValueError("dynamic state cannot move backward in time")
    if days == 0:
        return state

    decay = exp(-log(2.0) * days / config.mean_reversion_half_life_days)
    added_variance = config.process_variance_per_day * days
    return DynamicPlayerState(
        serve_mean=state.serve_mean * decay,
        serve_variance=min(
            config.max_variance,
            state.serve_variance + added_variance,
        ),
        return_mean=state.return_mean * decay,
        return_variance=min(
            config.max_variance,
            state.return_variance + added_variance,
        ),
        prior_serve_points=state.prior_serve_points,
        prior_return_points=state.prior_return_points,
        last_update_date=event_date,
    )


def _posterior_update(
    *,
    mean: float,
    variance: float,
    update: _UpdateAccumulator,
    min_variance: float,
) -> tuple[float, float]:
    if (
        update.information < 0.0
        or not isfinite(update.gradient)
        or not isfinite(update.information)
    ):
        raise ValueError("dynamic update contains invalid information")
    if update.information == 0.0:
        return mean, variance

    prior_precision = 1.0 / variance
    posterior_variance = max(
        min_variance,
        1.0 / (prior_precision + update.information),
    )
    posterior_mean = mean + posterior_variance * update.gradient
    return posterior_mean, posterior_variance


def walk_forward_dynamic_serve_return(
    matches: list[HistoricalMatch],
    *,
    config: DynamicServeReturnConfig | None = None,
    exclude_retirements: bool = True,
) -> list[DynamicServeReturnSnapshot]:
    """Build dynamic opponent-adjusted point state without same-day leakage.

    The latent serve and return parameters live on the service-point logit scale.
    Each source date is treated as an atomic batch:

    1. all players are advanced to the date using only prior-date state;
    2. every target snapshot for that date is emitted;
    3. score gradients/Fisher information from that date are accumulated against the
       same frozen state;
    4. one posterior update per player/role is committed after the date closes.

    This makes the update invariant to arbitrary within-date source row ordering.
    """

    config = config or DynamicServeReturnConfig()
    base_logit = _logit(config.base_service_win_rate)
    ordered = sorted(matches, key=lambda match: (match.pre_match.event_date, match.match_id))

    stored: dict[str, DynamicPlayerState] = {}
    snapshots: list[DynamicServeReturnSnapshot] = []

    for event_date, grouped in groupby(
        ordered,
        key=lambda match: match.pre_match.event_date,
    ):
        day_matches = [
            match
            for match in grouped
            if _eligible(match, exclude_retirements=exclude_retirements)
        ]
        if not day_matches:
            continue

        player_ids = {
            player_id
            for match in day_matches
            for player_id in (
                match.pre_match.player_a_id,
                match.pre_match.player_b_id,
            )
        }
        day_state: dict[str, DynamicPlayerState] = {}
        for player_id in player_ids:
            prior = stored.get(player_id)
            day_state[player_id] = (
                _new_state(event_date, config)
                if prior is None
                else _advance_state(prior, event_date=event_date, config=config)
            )

        serve_updates: defaultdict[str, _UpdateAccumulator] = defaultdict(
            _UpdateAccumulator
        )
        return_updates: defaultdict[str, _UpdateAccumulator] = defaultdict(
            _UpdateAccumulator
        )

        for match in day_matches:
            state = match.pre_match
            player_a = day_state[state.player_a_id]
            player_b = day_state[state.player_b_id]

            a_logit = base_logit + player_a.serve_mean - player_b.return_mean
            b_logit = base_logit + player_b.serve_mean - player_a.return_mean
            p_a_serve = _sigmoid(a_logit)
            p_b_serve = _sigmoid(b_logit)

            snapshots.append(
                DynamicServeReturnSnapshot(
                    match_id=match.match_id,
                    event_date=event_date,
                    probability_a_serve_point=p_a_serve,
                    probability_b_serve_point=p_b_serve,
                    matchup_edge_a=p_a_serve - p_b_serve,
                    serve_mean_a=player_a.serve_mean,
                    serve_mean_b=player_b.serve_mean,
                    return_mean_a=player_a.return_mean,
                    return_mean_b=player_b.return_mean,
                    serve_sd_a=sqrt(player_a.serve_variance),
                    serve_sd_b=sqrt(player_b.serve_variance),
                    return_sd_a=sqrt(player_a.return_variance),
                    return_sd_b=sqrt(player_b.return_variance),
                    a_serve_logit_sd=sqrt(
                        player_a.serve_variance + player_b.return_variance
                    ),
                    b_serve_logit_sd=sqrt(
                        player_b.serve_variance + player_a.return_variance
                    ),
                    prior_serve_points_a=player_a.prior_serve_points,
                    prior_serve_points_b=player_b.prior_serve_points,
                    prior_return_points_a=player_a.prior_return_points,
                    prior_return_points_b=player_b.prior_return_points,
                )
            )

            if match.stats is None:
                continue

            observations = (
                (
                    state.player_a_id,
                    state.player_b_id,
                    p_a_serve,
                    _service_observation(match.stats, side="a"),
                ),
                (
                    state.player_b_id,
                    state.player_a_id,
                    p_b_serve,
                    _service_observation(match.stats, side="b"),
                ),
            )
            for server_id, receiver_id, expected, observation in observations:
                if observation is None:
                    continue
                won, total = observation
                effective_total = total * config.point_information_weight
                effective_won = won * config.point_information_weight
                gradient = effective_won - effective_total * expected
                information = effective_total * expected * (1.0 - expected)

                serve_update = serve_updates[server_id]
                serve_update.gradient += gradient
                serve_update.information += information
                serve_update.points += total

                return_update = return_updates[receiver_id]
                return_update.gradient -= gradient
                return_update.information += information
                return_update.points += total

        for player_id in player_ids:
            prior = day_state[player_id]
            serve_update = serve_updates[player_id]
            return_update = return_updates[player_id]
            serve_mean, serve_variance = _posterior_update(
                mean=prior.serve_mean,
                variance=prior.serve_variance,
                update=serve_update,
                min_variance=config.min_variance,
            )
            return_mean, return_variance = _posterior_update(
                mean=prior.return_mean,
                variance=prior.return_variance,
                update=return_update,
                min_variance=config.min_variance,
            )
            stored[player_id] = DynamicPlayerState(
                serve_mean=serve_mean,
                serve_variance=serve_variance,
                return_mean=return_mean,
                return_variance=return_variance,
                prior_serve_points=prior.prior_serve_points + serve_update.points,
                prior_return_points=prior.prior_return_points + return_update.points,
                last_update_date=event_date,
            )

    return snapshots
