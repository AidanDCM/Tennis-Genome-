from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date
from itertools import groupby
from math import exp, log, log1p

from tennis_genome.data.canonical import HistoricalMatch, MatchStats
from tennis_genome.evaluation.walkforward import ModelPrediction, walk_forward_elo
from tennis_genome.ratings.serve_return import (
    ServeReturnConfig,
    ServeReturnSnapshot,
    walk_forward_serve_return,
)

_LOG_2 = log(2.0)


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

    def add(
        self,
        event_date: date,
        value: float,
        *,
        half_life_days: float,
        weight: float = 1.0,
    ) -> None:
        self._advance(event_date, half_life_days=half_life_days)
        self.numerator += value * weight
        self.weight += weight


@dataclass(frozen=True)
class FoundationalSnapshot:
    """Pre-match feature-family state built only from information before a date."""

    match_id: str
    event_date: date
    elo_logit: float
    serve_return_edge: float
    serve_rating_diff: float
    return_rating_diff: float
    min_prior_points: int

    form_result_30_diff: float
    form_result_90_diff: float
    form_point_30_diff: float
    form_point_90_diff: float

    event_gap_days_diff: float | None
    minutes_7_diff: float | None
    minutes_14_diff: float | None
    minutes_28_diff: float | None
    matches_14_diff: float
    matches_28_diff: float
    previous_event_minutes_diff: float | None

    age_diff: float | None
    age_curve_diff: float | None
    young_diff: float | None
    veteran_diff: float | None
    height_diff: float | None
    age_x_minutes_14_diff: float | None
    age_x_short_gap_diff: float | None

    h2h_edge: float
    h2h_weighted_edge: float
    h2h_count: int

    left_hand_diff: float
    opposite_hand_serve_edge: float

    surface_hard_elo: float
    surface_clay_elo: float
    surface_grass_elo: float
    surface_carpet_elo: float
    surface_hard_serve: float
    surface_clay_serve: float
    surface_grass_serve: float
    surface_carpet_serve: float
    slam_elo: float
    masters_elo: float
    finals_elo: float
    lower_tier_elo: float
    late_round_elo: float
    round_robin_elo: float
    best_of_five_elo: float
    qualifier_diff: float
    wildcard_diff: float
    lucky_loser_diff: float
    protected_ranking_diff: float
    seeded_diff: float
    seed_strength_diff: float


def _eligible(match: HistoricalMatch, *, exclude_retirements: bool) -> bool:
    if match.outcome.walkover:
        return False
    if exclude_retirements and match.outcome.retirement:
        return False
    return True


def _logit_probability(probability: float) -> float:
    clipped = min(max(probability, 1e-9), 1.0 - 1e-9)
    return log(clipped / (1.0 - clipped))


def _point_residual(
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
        return_residual_a = serve_snapshot.probability_b_serve_point - observed_b
        components.append((return_residual_a, stats.service_points_b))
    total = sum(weight for _, weight in components)
    if total <= 0:
        return None
    return sum(value * weight for value, weight in components) / total


def _window_minutes(
    values: list[tuple[date, int | None]],
    event_date: date,
    *,
    days: int,
) -> float | None:
    relevant = [
        duration
        for prior_date, duration in values
        if 0 < (event_date - prior_date).days <= days
    ]
    if not relevant:
        return 0.0
    if any(duration is None for duration in relevant):
        return None
    return float(sum(duration for duration in relevant if duration is not None))


def _window_values(
    history: deque[tuple[date, int | None]],
    event_date: date,
) -> tuple[float | None, float | None, float | None, float, float]:
    """Return recent workload windows without owning long-horizon rest state."""
    while history and (event_date - history[0][0]).days > 60:
        history.popleft()
    values = list(history)
    minutes_7 = _window_minutes(values, event_date, days=7)
    minutes_14 = _window_minutes(values, event_date, days=14)
    minutes_28 = _window_minutes(values, event_date, days=28)
    matches_14 = sum(
        1 for prior_date, _ in values if 0 < (event_date - prior_date).days <= 14
    )
    matches_28 = sum(
        1 for prior_date, _ in values if 0 < (event_date - prior_date).days <= 28
    )
    return (
        minutes_7,
        minutes_14,
        minutes_28,
        float(matches_14),
        float(matches_28),
    )


def _log1p_difference(a: float | int | None, b: float | int | None) -> float | None:
    if a is None or b is None:
        return None
    return log1p(float(a)) - log1p(float(b))


def _entry_indicator(entry: str | None, target: str) -> float:
    return 1.0 if (entry or "").upper() == target else 0.0


def _left_indicator(hand: str | None) -> float:
    return 1.0 if (hand or "").upper() == "L" else 0.0


def _known_opposite_hands(hand_a: str | None, hand_b: str | None) -> bool:
    a = (hand_a or "").upper()
    b = (hand_b or "").upper()
    return a in {"L", "R"} and b in {"L", "R"} and a != b


def _difference(a: float | int | None, b: float | int | None) -> float | None:
    if a is None or b is None:
        return None
    return float(a) - float(b)


def _age_curve(age: float | None) -> float | None:
    if age is None:
        return None
    return (age - 27.0) ** 2


def _binary_age(
    age: float | None,
    *,
    lower: float | None = None,
    upper: float | None = None,
) -> float | None:
    if age is None:
        return None
    if lower is not None:
        return 1.0 if age >= lower else 0.0
    if upper is not None:
        return 1.0 if age <= upper else 0.0
    raise ValueError("one age threshold must be supplied")


def walk_forward_foundational_features(
    matches: list[HistoricalMatch],
    *,
    serve_return_config: ServeReturnConfig | None = None,
    exclude_retirements: bool = True,
    precomputed_elo: list[ModelPrediction] | None = None,
    precomputed_serve_return: list[ServeReturnSnapshot] | None = None,
) -> list[FoundationalSnapshot]:
    """Build all currently-supported foundational families with frozen-date updates.

    Public source dates are event-start-era dates rather than trustworthy match
    start timestamps. Every feature state therefore freezes for a source date
    and updates only after every eligible match on that date has been observed.
    This deliberately discards possible within-event chronology rather than
    manufacturing it from match numbers or CSV row order.
    """
    eligible = [
        match
        for match in matches
        if _eligible(match, exclude_retirements=exclude_retirements)
    ]
    elo_predictions = (
        precomputed_elo
        if precomputed_elo is not None
        else walk_forward_elo(
            eligible,
            exclude_retirements=False,
        )
    )
    serve_snapshots = (
        precomputed_serve_return
        if precomputed_serve_return is not None
        else walk_forward_serve_return(
            eligible,
            config=serve_return_config,
            exclude_retirements=False,
        )
    )
    elo_map = {prediction.match_id: prediction for prediction in elo_predictions}
    serve_map = {snapshot.match_id: snapshot for snapshot in serve_snapshots}
    expected_match_ids = {match.match_id for match in eligible}
    missing_elo = expected_match_ids - elo_map.keys()
    missing_serve = expected_match_ids - serve_map.keys()
    if missing_elo or missing_serve:
        raise ValueError(
            "precomputed foundational components do not cover eligible matches: "
            f"elo={sorted(missing_elo)} serve_return={sorted(missing_serve)}"
        )
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
    h2h: defaultdict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    snapshots: list[FoundationalSnapshot] = []

    for event_date, grouped in groupby(
        ordered,
        key=lambda match: match.pre_match.event_date,
    ):
        day_matches = list(grouped)

        for match in day_matches:
            state = match.pre_match
            elo = elo_map[match.match_id]
            serve = serve_map[match.match_id]
            player_a = state.player_a_id
            player_b = state.player_b_id

            result_30_a = result_ema[30][player_a].mean_at(
                event_date,
                half_life_days=30.0,
            )
            result_30_b = result_ema[30][player_b].mean_at(
                event_date,
                half_life_days=30.0,
            )
            result_90_a = result_ema[90][player_a].mean_at(
                event_date,
                half_life_days=90.0,
            )
            result_90_b = result_ema[90][player_b].mean_at(
                event_date,
                half_life_days=90.0,
            )
            point_30_a = point_ema[30][player_a].mean_at(
                event_date,
                half_life_days=30.0,
            )
            point_30_b = point_ema[30][player_b].mean_at(
                event_date,
                half_life_days=30.0,
            )
            point_90_a = point_ema[90][player_a].mean_at(
                event_date,
                half_life_days=90.0,
            )
            point_90_b = point_ema[90][player_b].mean_at(
                event_date,
                half_life_days=90.0,
            )

            work_a = _window_values(workload[player_a], event_date)
            work_b = _window_values(workload[player_b], event_date)
            minutes_7_a, minutes_14_a, minutes_28_a, matches_14_a, matches_28_a = work_a
            minutes_7_b, minutes_14_b, minutes_28_b, matches_14_b, matches_28_b = work_b

            prior_date_a = last_event_date.get(player_a)
            prior_date_b = last_event_date.get(player_b)
            gap_a = (
                float((event_date - prior_date_a).days)
                if prior_date_a is not None
                else None
            )
            gap_b = (
                float((event_date - prior_date_b).days)
                if prior_date_b is not None
                else None
            )
            prev_a = last_event_minutes.get(player_a)
            prev_b = last_event_minutes.get(player_b)

            pair_key = (player_a, player_b)
            wins_a, wins_b = h2h[pair_key]
            h2h_count = wins_a + wins_b
            h2h_edge = (wins_a + 1.0) / (h2h_count + 2.0) - 0.5
            h2h_weighted = h2h_edge * log1p(h2h_count)

            age_diff = _difference(state.age_years_a, state.age_years_b)
            curve_diff = _difference(
                _age_curve(state.age_years_a),
                _age_curve(state.age_years_b),
            )
            young_diff = _difference(
                _binary_age(state.age_years_a, upper=23.0),
                _binary_age(state.age_years_b, upper=23.0),
            )
            veteran_diff = _difference(
                _binary_age(state.age_years_a, lower=32.0),
                _binary_age(state.age_years_b, lower=32.0),
            )
            height_diff = _difference(state.height_cm_a, state.height_cm_b)

            age_x_minutes: float | None = None
            age_x_short_gap: float | None = None
            if state.age_years_a is not None and state.age_years_b is not None:
                if minutes_14_a is not None and minutes_14_b is not None:
                    age_x_minutes = (
                        (state.age_years_a - 27.0) * log1p(minutes_14_a)
                        - (state.age_years_b - 27.0) * log1p(minutes_14_b)
                    )
                if gap_a is not None and gap_b is not None:
                    age_x_short_gap = (
                        (state.age_years_a - 27.0) * float(gap_a <= 7.0)
                        - (state.age_years_b - 27.0) * float(gap_b <= 7.0)
                    )

            left_diff = _left_indicator(state.hand_a) - _left_indicator(state.hand_b)
            opposite = _known_opposite_hands(state.hand_a, state.hand_b)
            surface = state.surface
            elo_logit = _logit_probability(elo.probability_a)
            serve_edge = serve.matchup_edge_a
            level = (state.tournament_level or "").upper()
            round_name = (state.round or "").upper()

            qualifier_diff = _entry_indicator(
                state.entry_a,
                "Q",
            ) - _entry_indicator(state.entry_b, "Q")
            wildcard_diff = _entry_indicator(
                state.entry_a,
                "WC",
            ) - _entry_indicator(state.entry_b, "WC")
            lucky_loser_diff = _entry_indicator(
                state.entry_a,
                "LL",
            ) - _entry_indicator(state.entry_b, "LL")
            protected_ranking_diff = _entry_indicator(
                state.entry_a,
                "PR",
            ) - _entry_indicator(state.entry_b, "PR")
            seeded_diff = float(state.seed_a is not None) - float(state.seed_b is not None)
            seed_strength_a = 1.0 / state.seed_a if state.seed_a else 0.0
            seed_strength_b = 1.0 / state.seed_b if state.seed_b else 0.0

            snapshots.append(
                FoundationalSnapshot(
                    match_id=match.match_id,
                    event_date=event_date,
                    elo_logit=elo_logit,
                    serve_return_edge=serve_edge,
                    serve_rating_diff=serve.serve_rating_diff_a,
                    return_rating_diff=serve.return_rating_diff_a,
                    min_prior_points=min(
                        serve.prior_serve_points_a,
                        serve.prior_serve_points_b,
                        serve.prior_return_points_a,
                        serve.prior_return_points_b,
                    ),
                    form_result_30_diff=result_30_a - result_30_b,
                    form_result_90_diff=result_90_a - result_90_b,
                    form_point_30_diff=point_30_a - point_30_b,
                    form_point_90_diff=point_90_a - point_90_b,
                    event_gap_days_diff=(
                        None if gap_a is None or gap_b is None else gap_a - gap_b
                    ),
                    minutes_7_diff=_log1p_difference(minutes_7_a, minutes_7_b),
                    minutes_14_diff=_log1p_difference(minutes_14_a, minutes_14_b),
                    minutes_28_diff=_log1p_difference(minutes_28_a, minutes_28_b),
                    matches_14_diff=matches_14_a - matches_14_b,
                    matches_28_diff=matches_28_a - matches_28_b,
                    previous_event_minutes_diff=_log1p_difference(prev_a, prev_b),
                    age_diff=age_diff,
                    age_curve_diff=curve_diff,
                    young_diff=young_diff,
                    veteran_diff=veteran_diff,
                    height_diff=height_diff,
                    age_x_minutes_14_diff=age_x_minutes,
                    age_x_short_gap_diff=age_x_short_gap,
                    h2h_edge=h2h_edge,
                    h2h_weighted_edge=h2h_weighted,
                    h2h_count=h2h_count,
                    left_hand_diff=left_diff,
                    opposite_hand_serve_edge=serve_edge * float(opposite),
                    surface_hard_elo=elo_logit * float(surface == "Hard"),
                    surface_clay_elo=elo_logit * float(surface == "Clay"),
                    surface_grass_elo=elo_logit * float(surface == "Grass"),
                    surface_carpet_elo=elo_logit * float(surface == "Carpet"),
                    surface_hard_serve=serve_edge * float(surface == "Hard"),
                    surface_clay_serve=serve_edge * float(surface == "Clay"),
                    surface_grass_serve=serve_edge * float(surface == "Grass"),
                    surface_carpet_serve=serve_edge * float(surface == "Carpet"),
                    slam_elo=elo_logit * float(level == "G"),
                    masters_elo=elo_logit * float(level == "M"),
                    finals_elo=elo_logit * float(level == "F"),
                    lower_tier_elo=elo_logit * float(level in {"C", "D"}),
                    late_round_elo=elo_logit * float(round_name in {"QF", "SF", "F"}),
                    round_robin_elo=elo_logit * float(round_name == "RR"),
                    best_of_five_elo=elo_logit * float(state.best_of == 5),
                    qualifier_diff=qualifier_diff,
                    wildcard_diff=wildcard_diff,
                    lucky_loser_diff=lucky_loser_diff,
                    protected_ranking_diff=protected_ranking_diff,
                    seeded_diff=seeded_diff,
                    seed_strength_diff=seed_strength_a - seed_strength_b,
                )
            )

        # Update every state only after all same-date snapshots have been frozen.
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

            y_a = 1.0 if match.outcome.a_won else 0.0
            result_residual_a = y_a - elo.probability_a
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

            point_residual_a = _point_residual(match.stats, serve)
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

            pair = h2h[(player_a, player_b)]
            if match.outcome.a_won:
                pair[0] += 1
            else:
                pair[1] += 1

        for player_id in day_players:
            last_event_date[player_id] = event_date
            last_event_minutes[player_id] = (
                None
                if player_id in day_missing_minutes
                else day_minutes[player_id]
            )

    return snapshots
