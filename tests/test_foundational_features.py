from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from tennis_genome.data.canonical import (
    HistoricalMatch,
    MatchOutcome,
    MatchStats,
    PreMatchState,
)
from tennis_genome.data.sackmann import load_sackmann_csv
from tennis_genome.features.foundational import walk_forward_foundational_features


def _match(
    *,
    match_id: str,
    event_date: date,
    player_a: str,
    player_b: str,
    a_won: bool,
    duration: int | None = 90,
    age_a: float = 25.0,
    age_b: float = 30.0,
    hand_a: str = "L",
    hand_b: str = "R",
) -> HistoricalMatch:
    return HistoricalMatch(
        pre_match=PreMatchState(
            match_id=match_id,
            tour="ATP",
            event_date=event_date,
            source_order=0,
            tournament_id=f"event-{event_date.year}",
            tournament_name="Synthetic Open",
            tournament_level="A",
            surface="Hard",
            round="R32",
            best_of=3,
            player_a_id=player_a,
            player_b_id=player_b,
            player_a_name=player_a,
            player_b_name=player_b,
            rank_a=10,
            rank_b=20,
            rank_points_a=2000,
            rank_points_b=1000,
            age_years_a=age_a,
            age_years_b=age_b,
            hand_a=hand_a,
            hand_b=hand_b,
            height_cm_a=190,
            height_cm_b=180,
        ),
        outcome=MatchOutcome(
            match_id=match_id,
            a_won=a_won,
            score="6-4 6-4",
            retirement=False,
            walkover=False,
        ),
        stats=MatchStats(
            match_id=match_id,
            service_points_a=60,
            service_points_b=60,
            first_serve_points_won_a=30 if a_won else 24,
            second_serve_points_won_a=12 if a_won else 10,
            first_serve_points_won_b=24 if a_won else 30,
            second_serve_points_won_b=10 if a_won else 12,
            duration_minutes=duration,
        ),
    )


def test_same_day_matches_do_not_update_each_other() -> None:
    matches = [
        _match(
            match_id="m1",
            event_date=date(2024, 1, 1),
            player_a="a",
            player_b="b",
            a_won=True,
        ),
        _match(
            match_id="m2",
            event_date=date(2024, 1, 1),
            player_a="a",
            player_b="b",
            a_won=False,
        ),
    ]

    snapshots = {item.match_id: item for item in walk_forward_foundational_features(matches)}

    assert snapshots["m1"].h2h_count == 0
    assert snapshots["m2"].h2h_count == 0
    assert snapshots["m1"].minutes_14_diff == snapshots["m2"].minutes_14_diff == 0.0
    assert snapshots["m1"].form_result_30_diff == snapshots["m2"].form_result_30_diff


def test_later_date_sees_prior_workload_form_and_h2h() -> None:
    matches = [
        _match(
            match_id="m1",
            event_date=date(2024, 1, 1),
            player_a="a",
            player_b="b",
            a_won=True,
            duration=120,
        ),
        _match(
            match_id="m2",
            event_date=date(2024, 1, 8),
            player_a="a",
            player_b="b",
            a_won=True,
            duration=80,
        ),
    ]

    snapshots = {item.match_id: item for item in walk_forward_foundational_features(matches)}
    later = snapshots["m2"]

    assert later.h2h_count == 1
    assert later.h2h_edge > 0.0
    assert later.form_result_30_diff > 0.0
    assert later.previous_event_minutes_diff == 0.0


def test_long_rest_gap_survives_recent_workload_pruning() -> None:
    matches = [
        _match(
            match_id="a-old",
            event_date=date(2024, 1, 1),
            player_a="a",
            player_b="c",
            a_won=True,
        ),
        _match(
            match_id="b-recent",
            event_date=date(2024, 3, 20),
            player_a="b",
            player_b="d",
            a_won=True,
        ),
        _match(
            match_id="target",
            event_date=date(2024, 4, 10),
            player_a="a",
            player_b="b",
            a_won=True,
        ),
    ]

    snapshots = {item.match_id: item for item in walk_forward_foundational_features(matches)}
    target = snapshots["target"]

    # A's 100-day gap remains available even though its rolling workload row was pruned.
    assert target.event_gap_days_diff == 79.0
    assert target.minutes_28_diff is not None
    assert target.minutes_28_diff < 0.0


def test_unknown_duration_is_not_treated_as_zero_workload() -> None:
    matches = [
        _match(
            match_id="a-missing",
            event_date=date(2024, 1, 1),
            player_a="a",
            player_b="c",
            a_won=True,
            duration=None,
        ),
        _match(
            match_id="b-known",
            event_date=date(2024, 1, 1),
            player_a="b",
            player_b="d",
            a_won=True,
            duration=90,
        ),
        _match(
            match_id="target",
            event_date=date(2024, 1, 8),
            player_a="a",
            player_b="b",
            a_won=True,
        ),
    ]

    snapshots = {item.match_id: item for item in walk_forward_foundational_features(matches)}
    target = snapshots["target"]

    assert target.minutes_14_diff is None
    assert target.previous_event_minutes_diff is None
    assert target.matches_14_diff == 0.0


def test_sackmann_demographics_and_duration_follow_canonical_orientation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "matches.csv"
    pd.DataFrame(
        [
            {
                "tourney_id": "2025-001",
                "tourney_name": "Orientation Open",
                "surface": "Clay",
                "draw_size": 32,
                "tourney_level": "A",
                "tourney_date": 20250101,
                "match_num": 1,
                "winner_id": 200,
                "winner_name": "Winner",
                "winner_seed": 2,
                "winner_entry": "WC",
                "winner_hand": "L",
                "winner_ht": 195,
                "winner_ioc": "USA",
                "winner_age": 31.5,
                "loser_id": 100,
                "loser_name": "Loser",
                "loser_seed": 8,
                "loser_entry": "Q",
                "loser_hand": "R",
                "loser_ht": 180,
                "loser_ioc": "ESP",
                "loser_age": 22.25,
                "score": "6-4 6-4",
                "best_of": 3,
                "round": "QF",
                "minutes": 105,
            }
        ]
    ).to_csv(source, index=False)

    match = load_sackmann_csv(source, tour="ATP")[0]
    state = match.pre_match

    assert state.player_a_id == "atp:id:100"
    assert state.player_b_id == "atp:id:200"
    assert state.hand_a == "R"
    assert state.hand_b == "L"
    assert state.age_years_a == 22.25
    assert state.age_years_b == 31.5
    assert state.height_cm_a == 180
    assert state.height_cm_b == 195
    assert state.entry_a == "Q"
    assert state.entry_b == "WC"
    assert state.seed_a == 8
    assert state.seed_b == 2
    assert state.ioc_a == "ESP"
    assert state.ioc_b == "USA"
    assert match.stats is not None
    assert match.stats.duration_minutes == 105
