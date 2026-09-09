from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from itertools import groupby
from math import exp, log

from tennis_genome.data.canonical import HistoricalMatch, MatchStats


@dataclass(frozen=True)
class ServeReturnConfig:
    """Configuration for the first opponent-adjusted point-strength experiment."""

    base_service_win_rate: float = 0.62
    learning_rate: float = 0.50
    reference_points: float = 60.0

    def __post_init__(self) -> None:
        if not 0.0 < self.base_service_win_rate < 1.0:
            raise ValueError("base_service_win_rate must be between zero and one")
        if self.learning_rate <= 0.0:
            raise ValueError("learning_rate must be positive")
        if self.reference_points <= 0.0:
            raise ValueError("reference_points must be positive")


@dataclass(frozen=True)
class ServeReturnSnapshot:
    """Serve/return information available immediately before a match date."""

    match_id: str
    event_date: date
    probability_a_serve_point: float
    probability_b_serve_point: float
    matchup_edge_a: float
    prior_serve_points_a: int
    prior_serve_points_b: int
    prior_return_points_a: int
    prior_return_points_b: int
    serve_rating_a: float
    serve_rating_b: float
    return_rating_a: float
    return_rating_b: float
    serve_rating_diff_a: float
    return_rating_diff_a: float


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


def walk_forward_serve_return(
    matches: list[HistoricalMatch],
    *,
    config: ServeReturnConfig | None = None,
    exclude_retirements: bool = True,
) -> list[ServeReturnSnapshot]:
    """Build opponent-adjusted serve/return strength without same-day leakage.

    Each service-point observation is modeled as a contest between the server's
    serve rating and the receiver's return rating. Ratings are frozen for an
    entire date, all residual updates are accumulated, and only then are they
    applied. Target-match statistics therefore cannot influence that match's
    own snapshot, even when a source file has only event dates and arbitrary row
    order rather than trustworthy start timestamps.
    """
    config = config or ServeReturnConfig()
    base_logit = _logit(config.base_service_win_rate)
    ordered = sorted(matches, key=lambda match: (match.pre_match.event_date, match.match_id))

    serve_rating: dict[str, float] = {}
    return_rating: dict[str, float] = {}
    serve_points: defaultdict[str, int] = defaultdict(int)
    return_points: defaultdict[str, int] = defaultdict(int)
    snapshots: list[ServeReturnSnapshot] = []

    for event_date, grouped in groupby(ordered, key=lambda match: match.pre_match.event_date):
        day_matches = [
            match
            for match in grouped
            if _eligible(match, exclude_retirements=exclude_retirements)
        ]
        serve_deltas: defaultdict[str, float] = defaultdict(float)
        return_deltas: defaultdict[str, float] = defaultdict(float)
        serve_point_additions: defaultdict[str, int] = defaultdict(int)
        return_point_additions: defaultdict[str, int] = defaultdict(int)

        for match in day_matches:
            state = match.pre_match
            serve_a = serve_rating.get(state.player_a_id, 0.0)
            serve_b = serve_rating.get(state.player_b_id, 0.0)
            return_a = return_rating.get(state.player_a_id, 0.0)
            return_b = return_rating.get(state.player_b_id, 0.0)
            p_a_serve = _sigmoid(base_logit + serve_a - return_b)
            p_b_serve = _sigmoid(base_logit + serve_b - return_a)
            snapshots.append(
                ServeReturnSnapshot(
                    match_id=match.match_id,
                    event_date=event_date,
                    probability_a_serve_point=p_a_serve,
                    probability_b_serve_point=p_b_serve,
                    matchup_edge_a=p_a_serve - p_b_serve,
                    prior_serve_points_a=serve_points[state.player_a_id],
                    prior_serve_points_b=serve_points[state.player_b_id],
                    prior_return_points_a=return_points[state.player_a_id],
                    prior_return_points_b=return_points[state.player_b_id],
                    serve_rating_a=serve_a,
                    serve_rating_b=serve_b,
                    return_rating_a=return_a,
                    return_rating_b=return_b,
                    serve_rating_diff_a=serve_a - serve_b,
                    return_rating_diff_a=return_a - return_b,
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
                observed_rate = won / total
                point_weight = min(total / config.reference_points, 1.0)
                combined_delta = (
                    config.learning_rate * point_weight * (observed_rate - expected)
                )
                serve_deltas[server_id] += 0.5 * combined_delta
                return_deltas[receiver_id] -= 0.5 * combined_delta
                serve_point_additions[server_id] += total
                return_point_additions[receiver_id] += total

        for player_id, delta in serve_deltas.items():
            serve_rating[player_id] = serve_rating.get(player_id, 0.0) + delta
        for player_id, delta in return_deltas.items():
            return_rating[player_id] = return_rating.get(player_id, 0.0) + delta
        for player_id, points in serve_point_additions.items():
            serve_points[player_id] += points
        for player_id, points in return_point_additions.items():
            return_points[player_id] += points

    return snapshots
