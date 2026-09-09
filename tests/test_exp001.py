from datetime import date

from tennis_genome.experiments.exp001 import run_exp001
from tests.factories import make_match


def test_exp001_compares_same_population_and_reports_years():
    matches = [
        make_match(
            match_id="2024-a",
            event_date=date(2024, 1, 1),
            player_a_id="p1",
            player_b_id="p2",
            a_won=True,
            rank_a=10,
            rank_b=50,
        ),
        make_match(
            match_id="2024-b",
            event_date=date(2024, 1, 2),
            player_a_id="p3",
            player_b_id="p4",
            a_won=False,
            rank_a=20,
            rank_b=40,
        ),
        make_match(
            match_id="2024-c",
            event_date=date(2024, 1, 3),
            player_a_id="p5",
            player_b_id="p6",
            a_won=True,
            rank_a=5,
            rank_b=80,
        ),
        make_match(
            match_id="2024-d",
            event_date=date(2024, 1, 4),
            player_a_id="p7",
            player_b_id="p8",
            a_won=False,
            rank_a=60,
            rank_b=15,
        ),
        make_match(
            match_id="2025-a",
            event_date=date(2025, 1, 1),
            player_a_id="p1",
            player_b_id="p3",
            a_won=True,
            rank_a=8,
            rank_b=30,
        ),
        make_match(
            match_id="2025-b",
            event_date=date(2025, 1, 2),
            player_a_id="p4",
            player_b_id="p2",
            a_won=False,
            rank_a=35,
            rank_b=12,
        ),
        make_match(
            match_id="2026-a",
            event_date=date(2026, 1, 1),
            player_a_id="p1",
            player_b_id="p4",
            a_won=True,
            rank_a=7,
            rank_b=25,
        ),
    ]

    report = run_exp001(matches, min_train_matches=4)

    assert report.experiment_id == "EXP-001"
    assert report.population_n == 3
    assert report.ranking.n == 3
    assert report.elo.n == 3
    assert [period.year for period in report.yearly] == [2025, 2026]
    assert [period.n for period in report.yearly] == [2, 1]
    assert 0.0 <= report.ranking.ece_10 <= 1.0
    assert 0.0 <= report.elo.ece_10 <= 1.0
