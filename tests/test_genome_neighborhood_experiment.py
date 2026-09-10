from __future__ import annotations

from datetime import date

import pytest

from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, PreMatchState
from tennis_genome.experiments.genome_neighborhood import run_genome_neighborhood


def _synthetic_match(year: int, index: int) -> HistoricalMatch:
    surface = ("Hard", "Clay", "Grass")[index % 3]
    level = ("A", "G", "M")[index % 3]
    round_name = ("R32", "QF", "SF", "F")[index % 4]
    player_a = f"a-{year}-{index:03d}"
    player_b = f"b-{year}-{index:03d}"
    state = PreMatchState(
        match_id=f"m-{year}-{index:03d}",
        tour="ATP",
        event_date=date(year, 1 + (index % 12), 1),
        source_order=index,
        tournament_id=f"event-{year}-{index // 32}",
        tournament_name="Synthetic Event",
        tournament_level=level,
        surface=surface,
        round=round_name,
        best_of=5 if index % 11 == 0 else 3,
        player_a_id=player_a,
        player_b_id=player_b,
        player_a_name=player_a,
        player_b_name=player_b,
        rank_a=1 + (index % 100),
        rank_b=1 + ((index * 7) % 100),
        rank_points_a=5000 - (index % 1000),
        rank_points_b=4500 - ((index * 3) % 1000),
        seed_a=(1 + index % 16) if index % 4 == 0 else None,
        seed_b=(1 + (index * 3) % 16) if index % 5 == 0 else None,
        entry_a="Q" if index % 17 == 0 else None,
        entry_b="WC" if index % 19 == 0 else None,
        hand_a="R",
        hand_b="L" if index % 5 == 0 else "R",
        height_cm_a=178 + (index % 15),
        height_cm_b=176 + ((index * 2) % 15),
        age_years_a=20.0 + (index % 15),
        age_years_b=21.0 + ((index * 3) % 15),
        ioc_a="USA",
        ioc_b="ESP",
    )
    return HistoricalMatch(
        pre_match=state,
        outcome=MatchOutcome(
            match_id=state.match_id,
            a_won=(index % 2 == 0),
            score="6-4 6-4",
            retirement=False,
            walkover=False,
        ),
        stats=None,
    )


def _history() -> list[HistoricalMatch]:
    return [
        _synthetic_match(year, index)
        for year in range(2010, 2016)
        for index in range(120)
    ]


def test_genome_experiment_runs_nested_chronology_with_registered_k() -> None:
    report = run_genome_neighborhood(
        _history(),
        tour="ATP",
        min_core_train_matches=100,
        min_neighbor_pool=250,
        min_meta_train_rows=50,
        candidate_limit=300,
    )

    assert report.primary_k == 100
    assert report.secondary_k == (25, 250)
    assert report.neighbor_population_n > 0
    assert report.meta_population_n > 0
    assert report.comparison.n == report.meta_population_n
    assert report.predictions
    assert min(row.year for row in report.predictions) >= 2015
    assert all(len(row.neighbor_ids_digest_100) == 64 for row in report.predictions)


def test_unique_player_history_gives_full_shared_player_exclusion_coverage() -> None:
    report = run_genome_neighborhood(
        _history(),
        tour="ATP",
        min_core_train_matches=100,
        min_neighbor_pool=250,
        min_meta_train_rows=50,
        candidate_limit=300,
    )

    sensitivity = report.shared_player_sensitivity
    assert sensitivity.coverage == pytest.approx(1.0)
    assert sensitivity.eligible_neighbor_rows == sensitivity.primary_neighbor_rows


def test_genome_experiment_rejects_spent_post_2025_data() -> None:
    matches = _history()
    matches.append(_synthetic_match(2026, 0))

    with pytest.raises(ValueError, match="post-2025"):
        run_genome_neighborhood(
            matches,
            tour="ATP",
            min_core_train_matches=100,
            min_neighbor_pool=250,
            min_meta_train_rows=50,
            candidate_limit=300,
        )


def test_candidate_limit_must_support_registered_250_neighbor_diagnostic() -> None:
    with pytest.raises(ValueError, match="at least 250"):
        run_genome_neighborhood(
            _history(),
            tour="ATP",
            min_core_train_matches=100,
            min_neighbor_pool=250,
            min_meta_train_rows=50,
            candidate_limit=249,
        )
