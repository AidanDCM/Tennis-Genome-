from __future__ import annotations

import pytest

from tennis_genome.simulation.tennis import (
    game_win_probability,
    match_win_probability,
    point_sim_match_probability,
    set_win_probability,
    tiebreak_win_probability,
)


def test_standard_game_probability_is_symmetric() -> None:
    assert game_win_probability(0.5) == pytest.approx(0.5)
    assert game_win_probability(0.0) == 0.0
    assert game_win_probability(1.0) == 1.0


def test_tiebreak_swap_symmetry() -> None:
    forward = tiebreak_win_probability(0.67, 0.61, first_server_a=True)
    reverse = tiebreak_win_probability(0.61, 0.67, first_server_a=False)
    assert forward == pytest.approx(1.0 - reverse, abs=1e-12)


def test_set_swap_symmetry() -> None:
    forward = set_win_probability(0.68, 0.60, first_server_a=True)
    reverse = set_win_probability(0.60, 0.68, first_server_a=False)
    assert forward == pytest.approx(1.0 - reverse, abs=1e-12)


@pytest.mark.parametrize("best_of", [3, 5])
def test_point_sim_player_swap_inverts_probability(best_of: int) -> None:
    forward = point_sim_match_probability(0.68, 0.60, best_of=best_of)
    reverse = point_sim_match_probability(0.60, 0.68, best_of=best_of)
    assert forward == pytest.approx(1.0 - reverse, abs=1e-12)


@pytest.mark.parametrize("best_of", [3, 5])
def test_equal_point_strength_is_even_match(best_of: int) -> None:
    probability = point_sim_match_probability(0.64, 0.64, best_of=best_of)
    assert probability == pytest.approx(0.5, abs=1e-12)


@pytest.mark.parametrize("best_of", [3, 5])
def test_probability_is_monotone_in_each_players_serve_strength(best_of: int) -> None:
    base = point_sim_match_probability(0.64, 0.62, best_of=best_of)
    stronger_a = point_sim_match_probability(0.66, 0.62, best_of=best_of)
    stronger_b = point_sim_match_probability(0.64, 0.64, best_of=best_of)
    assert stronger_a > base
    assert stronger_b < base


def test_best_of_five_amplifies_a_set_edge() -> None:
    best_of_three = match_win_probability(0.60, best_of=3)
    best_of_five = match_win_probability(0.60, best_of=5)
    assert best_of_five > best_of_three > 0.5


def test_invalid_probabilities_and_format_fail_closed() -> None:
    with pytest.raises(ValueError, match="between zero and one"):
        game_win_probability(1.01)
    with pytest.raises(ValueError, match="best_of"):
        point_sim_match_probability(0.64, 0.62, best_of=1)
