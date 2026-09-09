from __future__ import annotations

from datetime import date

from tennis_genome.data.canonical import (
    HistoricalMatch,
    MatchOutcome,
    PreMatchState,
    Surface,
)


def make_match(
    *,
    match_id: str,
    event_date: date,
    player_a_id: str,
    player_b_id: str,
    a_won: bool,
    rank_a: int | None = None,
    rank_b: int | None = None,
    surface: Surface = "Hard",
    retirement: bool = False,
    walkover: bool = False,
) -> HistoricalMatch:
    state = PreMatchState(
        match_id=match_id,
        tour="ATP",
        event_date=event_date,
        source_order=0,
        tournament_id="test",
        tournament_name="Test Event",
        tournament_level="A",
        surface=surface,
        round="R32",
        best_of=3,
        player_a_id=player_a_id,
        player_b_id=player_b_id,
        player_a_name=player_a_id,
        player_b_name=player_b_id,
        rank_a=rank_a,
        rank_b=rank_b,
        rank_points_a=None,
        rank_points_b=None,
    )
    outcome = MatchOutcome(
        match_id=match_id,
        a_won=a_won,
        score=None,
        retirement=retirement,
        walkover=walkover,
    )
    return HistoricalMatch(pre_match=state, outcome=outcome)
