from datetime import date

import pytest

from tennis_genome.experiments.exp002 import run_exp002
from tennis_genome.ratings.elo import EloConfig
from tests.factories import make_match


def test_exp002_uses_known_surface_population_and_reports_slices():
    matches = [
        make_match(
            match_id="2025-hard-1",
            event_date=date(2025, 1, 1),
            player_a_id="a",
            player_b_id="b",
            a_won=True,
            surface="Hard",
        ),
        make_match(
            match_id="2025-clay-1",
            event_date=date(2025, 4, 1),
            player_a_id="a",
            player_b_id="b",
            a_won=False,
            surface="Clay",
        ),
        make_match(
            match_id="2026-hard-1",
            event_date=date(2026, 1, 1),
            player_a_id="a",
            player_b_id="b",
            a_won=True,
            surface="Hard",
        ),
        make_match(
            match_id="2026-clay-1",
            event_date=date(2026, 4, 1),
            player_a_id="a",
            player_b_id="b",
            a_won=False,
            surface="Clay",
        ),
        make_match(
            match_id="unknown",
            event_date=date(2026, 5, 1),
            player_a_id="a",
            player_b_id="b",
            a_won=True,
            surface="Unknown",
        ),
    ]

    report = run_exp002(
        matches,
        config=EloConfig(initial_rating=1400.0, k_factor=24.0, scale=350.0),
    )

    assert report.experiment_id == "EXP-002"
    assert report.population_n == 4
    assert report.elo.n == 4
    assert report.surface_elo.n == 4
    assert report.initial_rating == pytest.approx(1400.0)
    assert report.k_factor == pytest.approx(24.0)
    assert report.scale == pytest.approx(350.0)
    assert [(item.slice_value, item.n) for item in report.yearly] == [
        ("2025", 2),
        ("2026", 2),
    ]
    assert [(item.slice_value, item.n) for item in report.by_surface] == [
        ("Clay", 2),
        ("Hard", 2),
    ]


def test_exp002_fails_when_all_surfaces_are_unknown():
    matches = [
        make_match(
            match_id="unknown",
            event_date=date(2026, 1, 1),
            player_a_id="a",
            player_b_id="b",
            a_won=True,
            surface="Unknown",
        )
    ]

    with pytest.raises(ValueError, match="known-surface"):
        run_exp002(matches)
