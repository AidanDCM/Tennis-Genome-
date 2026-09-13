from __future__ import annotations

from functools import cache
from math import comb

import numpy as np

_EPSILON = 1e-12


def _validate_probability(value: float, *, name: str) -> float:
    probability = float(value)
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"{name} must be between zero and one")
    return probability


def game_win_probability(point_win_probability: float) -> float:
    """Exact probability the server wins a standard advantage game."""
    p = _validate_probability(point_win_probability, name="point_win_probability")
    q = 1.0 - p
    if p <= _EPSILON:
        return 0.0
    if q <= _EPSILON:
        return 1.0

    win_before_deuce = p**4 * (1.0 + 4.0 * q + 10.0 * q**2)
    reach_deuce = 20.0 * p**3 * q**3
    win_from_deuce = p**2 / (p**2 + q**2)
    return win_before_deuce + reach_deuce * win_from_deuce


def _point_probability_a(
    *,
    phase: int,
    first_server_a: bool,
    p_a_serve: float,
    p_b_serve: float,
) -> float:
    cycle = (True, False, False, True)
    server_is_first = cycle[phase % 4]
    server_is_a = server_is_first if first_server_a else not server_is_first
    return p_a_serve if server_is_a else 1.0 - p_b_serve


def _tiebreak_deuce_probability(
    *,
    first_server_a: bool,
    p_a_serve: float,
    p_b_serve: float,
) -> float:
    """Solve the infinite win-by-two tiebreak tail from 6-6 exactly."""
    states = [(lead, phase) for lead in (-1, 0, 1) for phase in range(4)]
    index = {state: position for position, state in enumerate(states)}
    matrix = np.eye(len(states), dtype=float)
    rhs = np.zeros(len(states), dtype=float)

    for state_index, (lead, phase) in enumerate(states):
        p_a_point = _point_probability_a(
            phase=phase,
            first_server_a=first_server_a,
            p_a_serve=p_a_serve,
            p_b_serve=p_b_serve,
        )
        next_phase = (phase + 1) % 4

        win_lead = lead + 1
        if win_lead >= 2:
            rhs[state_index] += p_a_point
        else:
            matrix[state_index, index[(win_lead, next_phase)]] -= p_a_point

        loss_lead = lead - 1
        loss_probability = 1.0 - p_a_point
        if loss_lead <= -2:
            continue
        matrix[state_index, index[(loss_lead, next_phase)]] -= loss_probability

    solution = np.linalg.solve(matrix, rhs)
    return float(solution[index[(0, 0)]])


def tiebreak_win_probability(
    p_a_serve: float,
    p_b_serve: float,
    *,
    first_server_a: bool,
) -> float:
    """Probability A wins a standard first-to-seven, win-by-two tiebreak."""
    p_a = _validate_probability(p_a_serve, name="p_a_serve")
    p_b = _validate_probability(p_b_serve, name="p_b_serve")
    tail_probability = _tiebreak_deuce_probability(
        first_server_a=first_server_a,
        p_a_serve=p_a,
        p_b_serve=p_b,
    )

    @cache
    def recurse(a_points: int, b_points: int) -> float:
        if a_points >= 7 and a_points - b_points >= 2:
            return 1.0
        if b_points >= 7 and b_points - a_points >= 2:
            return 0.0
        if a_points == 6 and b_points == 6:
            return tail_probability

        phase = (a_points + b_points) % 4
        p_a_point = _point_probability_a(
            phase=phase,
            first_server_a=first_server_a,
            p_a_serve=p_a,
            p_b_serve=p_b,
        )
        return p_a_point * recurse(a_points + 1, b_points) + (1.0 - p_a_point) * recurse(
            a_points, b_points + 1
        )

    return recurse(0, 0)


def set_win_probability(
    p_a_serve: float,
    p_b_serve: float,
    *,
    first_server_a: bool,
) -> float:
    """Probability A wins a standard tiebreak set for a fixed first server."""
    p_a = _validate_probability(p_a_serve, name="p_a_serve")
    p_b = _validate_probability(p_b_serve, name="p_b_serve")
    hold_a = game_win_probability(p_a)
    hold_b = game_win_probability(p_b)
    tiebreak = tiebreak_win_probability(
        p_a,
        p_b,
        first_server_a=first_server_a,
    )

    @cache
    def recurse(a_games: int, b_games: int) -> float:
        if a_games >= 6 and a_games - b_games >= 2:
            return 1.0
        if b_games >= 6 and b_games - a_games >= 2:
            return 0.0
        if a_games == 6 and b_games == 6:
            return tiebreak

        game_index = a_games + b_games
        server_a = first_server_a if game_index % 2 == 0 else not first_server_a
        p_a_game = hold_a if server_a else 1.0 - hold_b
        return p_a_game * recurse(a_games + 1, b_games) + (1.0 - p_a_game) * recurse(
            a_games, b_games + 1
        )

    return recurse(0, 0)


def match_win_probability(set_win_probability_a: float, *, best_of: int) -> float:
    """Probability A wins a best-of-3 or best-of-5 match from set probability."""
    p_set = _validate_probability(
        set_win_probability_a,
        name="set_win_probability_a",
    )
    if best_of not in (3, 5):
        raise ValueError("best_of must be 3 or 5")
    required = best_of // 2 + 1
    return sum(
        comb(best_of, won_sets) * p_set**won_sets * (1.0 - p_set) ** (best_of - won_sets)
        for won_sets in range(required, best_of + 1)
    )


def point_sim_match_probability(
    p_a_serve: float,
    p_b_serve: float,
    *,
    best_of: int,
) -> float:
    """POINTSIM-001 match probability after first-server averaging."""
    set_a_first = set_win_probability(
        p_a_serve,
        p_b_serve,
        first_server_a=True,
    )
    set_b_first = set_win_probability(
        p_a_serve,
        p_b_serve,
        first_server_a=False,
    )
    average_set_probability = 0.5 * (set_a_first + set_b_first)
    return match_win_probability(average_set_probability, best_of=best_of)
