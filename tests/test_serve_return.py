from datetime import date, timedelta

from tennis_genome.data.canonical import (
    HistoricalMatch,
    MatchOutcome,
    MatchStats,
    PreMatchState,
)
from tennis_genome.experiments.exp003 import run_exp003
from tennis_genome.ratings.serve_return import (
    ServeReturnConfig,
    walk_forward_serve_return,
)


def _match(
    *,
    match_id: str,
    event_date: date,
    player_a: str,
    player_b: str,
    a_won: bool,
    a_service_won: int = 65,
    b_service_won: int = 60,
) -> HistoricalMatch:
    state = PreMatchState(
        match_id=match_id,
        tour="ATP",
        event_date=event_date,
        source_order=0,
        tournament_id=f"event-{event_date.isoformat()}",
        tournament_name="Synthetic Open",
        tournament_level="A",
        surface="Hard",
        round="R32",
        best_of=3,
        player_a_id=player_a,
        player_b_id=player_b,
        player_a_name=player_a,
        player_b_name=player_b,
        rank_a=None,
        rank_b=None,
        rank_points_a=None,
        rank_points_b=None,
    )
    outcome = MatchOutcome(
        match_id=match_id,
        a_won=a_won,
        score="6-4 6-4",
        retirement=False,
        walkover=False,
    )
    stats = MatchStats(
        match_id=match_id,
        service_points_a=100,
        service_points_b=100,
        first_serve_points_won_a=a_service_won,
        first_serve_points_won_b=b_service_won,
        second_serve_points_won_a=0,
        second_serve_points_won_b=0,
    )
    return HistoricalMatch(pre_match=state, outcome=outcome, stats=stats)


def test_same_day_matches_share_frozen_pre_day_serve_return_state():
    day = date(2025, 1, 1)
    matches = [
        _match(
            match_id="m1",
            event_date=day,
            player_a="A",
            player_b="B",
            a_won=True,
            a_service_won=90,
        ),
        _match(
            match_id="m2",
            event_date=day,
            player_a="A",
            player_b="C",
            a_won=False,
            a_service_won=30,
        ),
    ]

    snapshots = {item.match_id: item for item in walk_forward_serve_return(matches)}

    assert snapshots["m1"].probability_a_serve_point == 0.62
    assert snapshots["m2"].probability_a_serve_point == 0.62
    assert snapshots["m1"].prior_serve_points_a == 0
    assert snapshots["m2"].prior_serve_points_a == 0


def test_prior_strong_service_stats_raise_next_day_server_expectation():
    day = date(2025, 1, 1)
    matches = [
        _match(
            match_id="m1",
            event_date=day,
            player_a="A",
            player_b="B",
            a_won=True,
            a_service_won=90,
            b_service_won=62,
        ),
        _match(
            match_id="m2",
            event_date=day + timedelta(days=1),
            player_a="A",
            player_b="C",
            a_won=True,
            a_service_won=65,
            b_service_won=60,
        ),
    ]

    snapshots = {item.match_id: item for item in walk_forward_serve_return(matches)}

    assert snapshots["m2"].probability_a_serve_point > 0.62
    assert snapshots["m2"].prior_serve_points_a == 100


def test_exp003_runs_only_after_prior_year_training_population_exists():
    start = date(2020, 1, 1)
    matches: list[HistoricalMatch] = []
    players = ["A", "B", "C", "D"]
    match_number = 0
    for year_offset in range(4):
        for index in range(12):
            match_number += 1
            player_a = players[index % len(players)]
            player_b = players[(index + 1) % len(players)]
            a_won = index % 3 != 0
            matches.append(
                _match(
                    match_id=f"m{match_number}",
                    event_date=date(start.year + year_offset, 1, 1)
                    + timedelta(days=index),
                    player_a=player_a,
                    player_b=player_b,
                    a_won=a_won,
                    a_service_won=72 if a_won else 55,
                    b_service_won=56 if a_won else 70,
                )
            )

    report = run_exp003(
        matches,
        config=ServeReturnConfig(),
        min_train_matches=10,
    )

    assert report.population_n == 36
    assert len(report.yearly) == 3
    assert report.elo_calibrated.n == report.elo_serve_return.n
    assert report.history_slices[0].min_prior_points == 0
