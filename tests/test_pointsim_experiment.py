from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from tennis_genome.data.canonical import HistoricalMatch
from tennis_genome.experiments.pointsim import run_pointsim
from tests.factories import make_match


def _history() -> list[HistoricalMatch]:
    players = ["P1", "P2", "P3", "P4", "P5", "P6"]
    matches: list[HistoricalMatch] = []
    for year in range(2018, 2026):
        for index in range(8):
            player_a = players[index % len(players)]
            player_b = players[(index + 1 + year) % len(players)]
            if player_a == player_b:
                player_b = players[(index + 2) % len(players)]
            matches.append(
                make_match(
                    match_id=f"{year}-{index}",
                    event_date=date(year, 1, index + 1),
                    player_a_id=player_a,
                    player_b_id=player_b,
                    a_won=(year + index) % 2 == 0,
                    rank_a=10 + index,
                    rank_b=20 + ((index * 3) % 11),
                )
            )
    return matches


def _run(matches: list[HistoricalMatch]):
    return run_pointsim(
        matches,
        tour="ATP",
        min_core_train_matches=8,
        min_model_train_rows=8,
    )


def test_outer_year_outcomes_cannot_change_outer_year_predictions() -> None:
    original = _history()
    changed = [
        HistoricalMatch(
            pre_match=match.pre_match,
            outcome=(
                replace(match.outcome, a_won=not match.outcome.a_won)
                if match.pre_match.event_date.year == 2025
                else match.outcome
            ),
            stats=match.stats,
        )
        for match in original
    ]

    first = _run(original)
    second = _run(changed)
    first_2025 = {
        row.match_id: (
            row.pointsim_probability_a,
            row.same_input_control_probability_a,
            row.core_control_probability_a,
            row.core_plus_pointsim_probability_a,
        )
        for row in first.predictions
        if row.year == 2025
    }
    second_2025 = {
        row.match_id: (
            row.pointsim_probability_a,
            row.same_input_control_probability_a,
            row.core_control_probability_a,
            row.core_plus_pointsim_probability_a,
        )
        for row in second.predictions
        if row.year == 2025
    }
    assert first_2025
    assert first_2025 == second_2025


def test_post_2025_selected_tour_rows_fail_closed() -> None:
    history = _history()
    history.append(
        make_match(
            match_id="2026-forbidden",
            event_date=date(2026, 1, 2),
            player_a_id="P1",
            player_b_id="P2",
            a_won=True,
            rank_a=10,
            rank_b=20,
        )
    )
    with pytest.raises(ValueError, match="post-2025"):
        _run(history)


def test_unsupported_best_of_is_excluded_not_inferred() -> None:
    history = _history()
    target_id = "2024-3"
    changed: list[HistoricalMatch] = []
    for match in history:
        if match.match_id == target_id:
            changed.append(
                HistoricalMatch(
                    pre_match=replace(match.pre_match, best_of=1),
                    outcome=match.outcome,
                    stats=match.stats,
                )
            )
        else:
            changed.append(match)

    report = _run(changed)
    assert target_id not in {row.match_id for row in report.predictions}
    assert report.supported_format_coverage < 1.0
