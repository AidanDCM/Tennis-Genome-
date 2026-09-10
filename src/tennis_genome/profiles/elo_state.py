from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from itertools import groupby

from tennis_genome.data.canonical import HistoricalMatch
from tennis_genome.ratings.elo import EloConfig, expected_score


@dataclass(frozen=True)
class EloStateSnapshot:
    """Absolute pre-match Elo state for both players in one match."""

    match_id: str
    event_date: date
    rating_a: float
    rating_b: float
    probability_a: float
    prior_matches_a: int
    prior_matches_b: int


def _eligible(match: HistoricalMatch, *, exclude_retirements: bool) -> bool:
    if match.outcome.walkover:
        return False
    if exclude_retirements and match.outcome.retirement:
        return False
    return True


def walk_forward_elo_state(
    matches: list[HistoricalMatch],
    *,
    config: EloConfig | None = None,
    exclude_retirements: bool = True,
) -> list[EloStateSnapshot]:
    """Return absolute Elo ratings with the project's frozen-date semantics."""
    config = config or EloConfig()
    ordered = sorted(
        matches,
        key=lambda match: (match.pre_match.event_date, match.match_id),
    )
    ratings: dict[str, float] = {}
    match_counts: defaultdict[str, int] = defaultdict(int)
    snapshots: list[EloStateSnapshot] = []

    for event_date, grouped in groupby(
        ordered,
        key=lambda match: match.pre_match.event_date,
    ):
        day_matches = [
            match
            for match in grouped
            if _eligible(match, exclude_retirements=exclude_retirements)
        ]
        deltas: defaultdict[str, float] = defaultdict(float)
        count_additions: defaultdict[str, int] = defaultdict(int)

        for match in day_matches:
            state = match.pre_match
            rating_a = ratings.get(state.player_a_id, config.initial_rating)
            rating_b = ratings.get(state.player_b_id, config.initial_rating)
            probability_a = expected_score(rating_a, rating_b, scale=config.scale)
            snapshots.append(
                EloStateSnapshot(
                    match_id=match.match_id,
                    event_date=event_date,
                    rating_a=rating_a,
                    rating_b=rating_b,
                    probability_a=probability_a,
                    prior_matches_a=match_counts[state.player_a_id],
                    prior_matches_b=match_counts[state.player_b_id],
                )
            )

            outcome_a = 1.0 if match.outcome.a_won else 0.0
            delta_a = config.k_factor * (outcome_a - probability_a)
            deltas[state.player_a_id] += delta_a
            deltas[state.player_b_id] -= delta_a
            count_additions[state.player_a_id] += 1
            count_additions[state.player_b_id] += 1

        for player_id, delta in deltas.items():
            ratings[player_id] = ratings.get(player_id, config.initial_rating) + delta
        for player_id, addition in count_additions.items():
            match_counts[player_id] += addition

    return snapshots
