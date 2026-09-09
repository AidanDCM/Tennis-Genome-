from __future__ import annotations

from datetime import date

from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, MatchStats, PreMatchState
from tennis_genome.experiments.family_lab import FAMILY_FEATURES, run_family_lab


def _match(index: int, year: int, a_won: bool) -> HistoricalMatch:
    player_a = f"a{index % 3}"
    player_b = f"b{index % 3}"
    match_id = f"m-{year}-{index}"
    return HistoricalMatch(
        pre_match=PreMatchState(
            match_id=match_id,
            tour="ATP",
            event_date=date(year, 1 + (index % 6), 1),
            source_order=index,
            tournament_id=f"event-{year}-{index}",
            tournament_name="Synthetic",
            tournament_level="A" if index % 2 else "G",
            surface="Hard" if index % 2 else "Clay",
            round="QF" if index % 3 == 0 else "R32",
            best_of=5 if index % 4 == 0 else 3,
            player_a_id=player_a,
            player_b_id=player_b,
            player_a_name=player_a,
            player_b_name=player_b,
            rank_a=10 + index,
            rank_b=30 + index,
            rank_points_a=2000,
            rank_points_b=1000,
            seed_a=1 if index % 2 else None,
            seed_b=None,
            entry_a=None,
            entry_b="Q" if index % 5 == 0 else None,
            hand_a="L" if index % 2 else "R",
            hand_b="R",
            height_cm_a=188,
            height_cm_b=182,
            age_years_a=24.0 + (index % 5),
            age_years_b=29.0 + (index % 4),
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
            first_serve_points_won_a=31 if a_won else 24,
            second_serve_points_won_a=12 if a_won else 9,
            first_serve_points_won_b=24 if a_won else 31,
            second_serve_points_won_b=9 if a_won else 12,
            duration_minutes=80 + index,
        ),
    )


def test_family_lab_scores_every_registered_family_on_common_population() -> None:
    matches: list[HistoricalMatch] = []
    for year in (2020, 2021, 2022, 2023):
        for index in range(12):
            matches.append(_match(index, year, a_won=(index + year) % 3 != 0))

    report = run_family_lab(matches, min_train_matches=10)

    assert report.population_n > 0
    assert report.evaluated_years >= 2
    assert {item.family for item in report.families} == set(FAMILY_FEATURES)
    assert all(item.add_one.n == report.population_n for item in report.families)
    assert all(item.full_minus_family.n == report.population_n for item in report.families)
    assert report.core.n == report.full.n == report.population_n
    assert report.serve_return_decomposition.elo_only.n == report.population_n
