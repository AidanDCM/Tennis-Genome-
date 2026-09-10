from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import date
from itertools import groupby
from math import exp, log

from tennis_genome.data.canonical import HistoricalMatch, MatchStats, Tour
from tennis_genome.profiles.elo_state import EloStateSnapshot, walk_forward_elo_state
from tennis_genome.ratings.serve_return import (
    ServeReturnConfig,
    ServeReturnSnapshot,
    walk_forward_serve_return,
)

_LOG_2 = log(2.0)
PROFILE_VERSION = "player-profile-v1"


@dataclass
class _DecayAccumulator:
    numerator: float = 0.0
    weight: float = 0.0
    last_date: date | None = None

    def _advance(self, event_date: date, *, half_life_days: float) -> None:
        if self.last_date is None:
            self.last_date = event_date
            return
        days = max((event_date - self.last_date).days, 0)
        if days:
            factor = exp(-_LOG_2 * days / half_life_days)
            self.numerator *= factor
            self.weight *= factor
            self.last_date = event_date

    def mean_at(self, event_date: date, *, half_life_days: float) -> float:
        self._advance(event_date, half_life_days=half_life_days)
        return self.numerator / self.weight if self.weight > 0.0 else 0.0

    def add(self, event_date: date, value: float, *, half_life_days: float) -> None:
        self._advance(event_date, half_life_days=half_life_days)
        self.numerator += value
        self.weight += 1.0


@dataclass(frozen=True)
class PlayerProfileSnapshot:
    """One player's legal pre-match state as of a historical source date.

    Descriptive fields are stored alongside validated dynamic state, but storage
    does not imply predictive promotion. Tour-specific predictive permissions
    live in ``profiles.spec`` and are deliberately separate from this object.
    """

    player_id: str
    player_name: str
    tour: Tour
    valid_from: date
    valid_until: date | None
    profile_version: str

    # Descriptive / source-observed state.
    ranking: int | None
    ranking_points: int | None
    age_years: float | None
    height_cm: int | None
    hand: str | None
    ioc: str | None

    # Outcome-based ability state.
    elo_rating: float
    prior_matches: int

    # Opponent-adjusted point-strength state.
    serve_rating: float
    return_rating: float
    prior_serve_points: int
    prior_return_points: int

    # Opponent-adjusted recent-form residual state.
    form_result_30: float
    form_result_90: float
    form_point_30: float
    form_point_90: float

    # Workload/rest state. Missing duration remains unknown, never fake zero.
    event_gap_days: float | None
    minutes_7: float | None
    minutes_14: float | None
    minutes_28: float | None
    matches_14: int
    matches_28: int
    previous_event_minutes: int | None

    # Data-depth / uncertainty descriptors.
    has_point_history: bool
    has_complete_14d_duration: bool

    @property
    def profile_hash(self) -> str:
        payload = asdict(self)
        payload["valid_from"] = self.valid_from.isoformat()
        payload["valid_until"] = (
            self.valid_until.isoformat() if self.valid_until is not None else None
        )
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MatchProfilePair:
    """Profiles presented to a match before that match/date can update state."""

    match_id: str
    event_date: date
    player_a: PlayerProfileSnapshot
    player_b: PlayerProfileSnapshot


def _eligible(match: HistoricalMatch, *, exclude_retirements: bool) -> bool:
    if match.outcome.walkover:
        return False
    if exclude_retirements and match.outcome.retirement:
        return False
    return True


def _service_point_residual(
    stats: MatchStats | None,
    serve_snapshot: ServeReturnSnapshot,
) -> float | None:
    if stats is None:
        return None
    components: list[tuple[float, int]] = []
    if (
        stats.service_points_a is not None
        and stats.service_points_won_a is not None
        and stats.service_points_a > 0
    ):
        observed = stats.service_points_won_a / stats.service_points_a
        components.append(
            (
                observed - serve_snapshot.probability_a_serve_point,
                stats.service_points_a,
            )
        )
    if (
        stats.service_points_b is not None
        and stats.service_points_won_b is not None
        and stats.service_points_b > 0
    ):
        observed_b = stats.service_points_won_b / stats.service_points_b
        components.append(
            (
                serve_snapshot.probability_b_serve_point - observed_b,
                stats.service_points_b,
            )
        )
    total = sum(weight for _, weight in components)
    if total <= 0:
        return None
    return sum(value * weight for value, weight in components) / total


def _window_minutes(
    history: deque[tuple[date, int | None]],
    event_date: date,
    *,
    days: int,
) -> float | None:
    relevant = [
        duration
        for prior_date, duration in history
        if 0 < (event_date - prior_date).days <= days
    ]
    if not relevant:
        return 0.0
    if any(duration is None for duration in relevant):
        return None
    return float(sum(duration for duration in relevant if duration is not None))


def _workload_state(
    history: deque[tuple[date, int | None]],
    event_date: date,
) -> tuple[float | None, float | None, float | None, int, int]:
    while history and (event_date - history[0][0]).days > 60:
        history.popleft()
    minutes_7 = _window_minutes(history, event_date, days=7)
    minutes_14 = _window_minutes(history, event_date, days=14)
    minutes_28 = _window_minutes(history, event_date, days=28)
    matches_14 = sum(
        1 for prior_date, _ in history if 0 < (event_date - prior_date).days <= 14
    )
    matches_28 = sum(
        1 for prior_date, _ in history if 0 < (event_date - prior_date).days <= 28
    )
    return minutes_7, minutes_14, minutes_28, matches_14, matches_28


def _profile_for_side(
    match: HistoricalMatch,
    *,
    side: str,
    elo: EloStateSnapshot,
    serve: ServeReturnSnapshot,
    event_date: date,
    result_ema: dict[int, defaultdict[str, _DecayAccumulator]],
    point_ema: dict[int, defaultdict[str, _DecayAccumulator]],
    workload: defaultdict[str, deque[tuple[date, int | None]]],
    last_event_date: dict[str, date],
    last_event_minutes: dict[str, int | None],
) -> PlayerProfileSnapshot:
    state = match.pre_match
    if side == "a":
        player_id = state.player_a_id
        player_name = state.player_a_name
        ranking = state.rank_a
        ranking_points = state.rank_points_a
        age_years = state.age_years_a
        height_cm = state.height_cm_a
        hand = state.hand_a
        ioc = state.ioc_a
        elo_rating = elo.rating_a
        prior_matches = elo.prior_matches_a
        serve_rating = serve.serve_rating_a
        return_rating = serve.return_rating_a
        prior_serve_points = serve.prior_serve_points_a
        prior_return_points = serve.prior_return_points_a
    elif side == "b":
        player_id = state.player_b_id
        player_name = state.player_b_name
        ranking = state.rank_b
        ranking_points = state.rank_points_b
        age_years = state.age_years_b
        height_cm = state.height_cm_b
        hand = state.hand_b
        ioc = state.ioc_b
        elo_rating = elo.rating_b
        prior_matches = elo.prior_matches_b
        serve_rating = serve.serve_rating_b
        return_rating = serve.return_rating_b
        prior_serve_points = serve.prior_serve_points_b
        prior_return_points = serve.prior_return_points_b
    else:
        raise ValueError(f"invalid profile side: {side!r}")

    minutes_7, minutes_14, minutes_28, matches_14, matches_28 = _workload_state(
        workload[player_id],
        event_date,
    )
    prior_date = last_event_date.get(player_id)
    event_gap_days = (
        float((event_date - prior_date).days) if prior_date is not None else None
    )
    previous_minutes = last_event_minutes.get(player_id)

    return PlayerProfileSnapshot(
        player_id=player_id,
        player_name=player_name,
        tour=state.tour,
        valid_from=event_date,
        valid_until=None,
        profile_version=PROFILE_VERSION,
        ranking=ranking,
        ranking_points=ranking_points,
        age_years=age_years,
        height_cm=height_cm,
        hand=hand,
        ioc=ioc,
        elo_rating=elo_rating,
        prior_matches=prior_matches,
        serve_rating=serve_rating,
        return_rating=return_rating,
        prior_serve_points=prior_serve_points,
        prior_return_points=prior_return_points,
        form_result_30=result_ema[30][player_id].mean_at(
            event_date,
            half_life_days=30.0,
        ),
        form_result_90=result_ema[90][player_id].mean_at(
            event_date,
            half_life_days=90.0,
        ),
        form_point_30=point_ema[30][player_id].mean_at(
            event_date,
            half_life_days=30.0,
        ),
        form_point_90=point_ema[90][player_id].mean_at(
            event_date,
            half_life_days=90.0,
        ),
        event_gap_days=event_gap_days,
        minutes_7=minutes_7,
        minutes_14=minutes_14,
        minutes_28=minutes_28,
        matches_14=matches_14,
        matches_28=matches_28,
        previous_event_minutes=previous_minutes,
        has_point_history=(prior_serve_points > 0 and prior_return_points > 0),
        has_complete_14d_duration=minutes_14 is not None,
    )


def walk_forward_player_profiles(
    matches: list[HistoricalMatch],
    *,
    serve_return_config: ServeReturnConfig | None = None,
    exclude_retirements: bool = True,
) -> list[MatchProfilePair]:
    """Build Player Profile v1 pairs without current-date outcome leakage.

    Ratings, form, point strength and workload are frozen for a source date.
    Every eligible match on that date sees the same prior dynamic state; only
    after all profiles for the date are emitted are that date's results/stats
    allowed to update the next state.
    """
    eligible = [
        match
        for match in matches
        if _eligible(match, exclude_retirements=exclude_retirements)
    ]
    elo_map = {
        snapshot.match_id: snapshot
        for snapshot in walk_forward_elo_state(
            eligible,
            exclude_retirements=False,
        )
    }
    serve_map = {
        snapshot.match_id: snapshot
        for snapshot in walk_forward_serve_return(
            eligible,
            config=serve_return_config,
            exclude_retirements=False,
        )
    }
    ordered = sorted(
        eligible,
        key=lambda match: (match.pre_match.event_date, match.match_id),
    )

    result_ema: dict[int, defaultdict[str, _DecayAccumulator]] = {
        30: defaultdict(_DecayAccumulator),
        90: defaultdict(_DecayAccumulator),
    }
    point_ema: dict[int, defaultdict[str, _DecayAccumulator]] = {
        30: defaultdict(_DecayAccumulator),
        90: defaultdict(_DecayAccumulator),
    }
    workload: defaultdict[str, deque[tuple[date, int | None]]] = defaultdict(deque)
    last_event_date: dict[str, date] = {}
    last_event_minutes: dict[str, int | None] = {}
    pairs: list[MatchProfilePair] = []

    for event_date, grouped in groupby(
        ordered,
        key=lambda match: match.pre_match.event_date,
    ):
        day_matches = list(grouped)

        for match in day_matches:
            elo = elo_map[match.match_id]
            serve = serve_map[match.match_id]
            pairs.append(
                MatchProfilePair(
                    match_id=match.match_id,
                    event_date=event_date,
                    player_a=_profile_for_side(
                        match,
                        side="a",
                        elo=elo,
                        serve=serve,
                        event_date=event_date,
                        result_ema=result_ema,
                        point_ema=point_ema,
                        workload=workload,
                        last_event_date=last_event_date,
                        last_event_minutes=last_event_minutes,
                    ),
                    player_b=_profile_for_side(
                        match,
                        side="b",
                        elo=elo,
                        serve=serve,
                        event_date=event_date,
                        result_ema=result_ema,
                        point_ema=point_ema,
                        workload=workload,
                        last_event_date=last_event_date,
                        last_event_minutes=last_event_minutes,
                    ),
                )
            )

        # Apply all current-date outcomes and stats only after profiles freeze.
        day_minutes: defaultdict[str, int] = defaultdict(int)
        day_missing_minutes: set[str] = set()
        day_players: set[str] = set()
        for match in day_matches:
            state = match.pre_match
            elo = elo_map[match.match_id]
            serve = serve_map[match.match_id]
            player_a = state.player_a_id
            player_b = state.player_b_id
            day_players.update((player_a, player_b))

            outcome_a = 1.0 if match.outcome.a_won else 0.0
            result_residual_a = outcome_a - elo.probability_a
            for half_life in (30, 90):
                result_ema[half_life][player_a].add(
                    event_date,
                    result_residual_a,
                    half_life_days=float(half_life),
                )
                result_ema[half_life][player_b].add(
                    event_date,
                    -result_residual_a,
                    half_life_days=float(half_life),
                )

            point_residual_a = _service_point_residual(match.stats, serve)
            if point_residual_a is not None:
                for half_life in (30, 90):
                    point_ema[half_life][player_a].add(
                        event_date,
                        point_residual_a,
                        half_life_days=float(half_life),
                    )
                    point_ema[half_life][player_b].add(
                        event_date,
                        -point_residual_a,
                        half_life_days=float(half_life),
                    )

            duration = match.stats.duration_minutes if match.stats is not None else None
            workload[player_a].append((event_date, duration))
            workload[player_b].append((event_date, duration))
            if duration is None:
                day_missing_minutes.update((player_a, player_b))
            else:
                day_minutes[player_a] += duration
                day_minutes[player_b] += duration

        for player_id in day_players:
            last_event_date[player_id] = event_date
            last_event_minutes[player_id] = (
                None if player_id in day_missing_minutes else day_minutes[player_id]
            )

    return pairs
