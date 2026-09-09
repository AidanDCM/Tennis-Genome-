from datetime import date

import pytest

from tennis_genome.evaluation.walkforward import (
    walk_forward_elo,
    walk_forward_ranking_logit,
    walk_forward_surface_elo,
)
from tests.factories import make_match


def test_same_day_matches_use_frozen_pre_day_elo():
    matches = [
        make_match(
            match_id="d1-m1",
            event_date=date(2026, 1, 1),
            player_a_id="a",
            player_b_id="b",
            a_won=True,
        ),
        make_match(
            match_id="d1-m2",
            event_date=date(2026, 1, 1),
            player_a_id="a",
            player_b_id="c",
            a_won=True,
        ),
        make_match(
            match_id="d2-m1",
            event_date=date(2026, 1, 2),
            player_a_id="a",
            player_b_id="d",
            a_won=True,
        ),
    ]

    predictions = {prediction.match_id: prediction for prediction in walk_forward_elo(matches)}

    assert predictions["d1-m1"].probability_a == pytest.approx(0.5)
    assert predictions["d1-m2"].probability_a == pytest.approx(0.5)
    assert predictions["d2-m1"].probability_a > 0.5


def test_surface_elo_keeps_surfaces_independent():
    matches = [
        make_match(
            match_id="hard-1",
            event_date=date(2026, 1, 1),
            player_a_id="a",
            player_b_id="b",
            a_won=True,
            surface="Hard",
        ),
        make_match(
            match_id="clay-1",
            event_date=date(2026, 1, 2),
            player_a_id="a",
            player_b_id="b",
            a_won=True,
            surface="Clay",
        ),
        make_match(
            match_id="hard-2",
            event_date=date(2026, 1, 3),
            player_a_id="a",
            player_b_id="b",
            a_won=True,
            surface="Hard",
        ),
        make_match(
            match_id="clay-2",
            event_date=date(2026, 1, 4),
            player_a_id="a",
            player_b_id="b",
            a_won=True,
            surface="Clay",
        ),
    ]

    predictions = {
        prediction.match_id: prediction for prediction in walk_forward_surface_elo(matches)
    }

    assert predictions["hard-1"].probability_a == pytest.approx(0.5)
    assert predictions["clay-1"].probability_a == pytest.approx(0.5)
    assert predictions["hard-2"].probability_a > 0.5
    assert predictions["clay-2"].probability_a > 0.5


def test_surface_elo_same_day_matches_use_frozen_surface_ratings():
    matches = [
        make_match(
            match_id="d1-hard-1",
            event_date=date(2026, 1, 1),
            player_a_id="a",
            player_b_id="b",
            a_won=True,
            surface="Hard",
        ),
        make_match(
            match_id="d1-hard-2",
            event_date=date(2026, 1, 1),
            player_a_id="a",
            player_b_id="c",
            a_won=True,
            surface="Hard",
        ),
        make_match(
            match_id="d2-hard",
            event_date=date(2026, 1, 2),
            player_a_id="a",
            player_b_id="d",
            a_won=True,
            surface="Hard",
        ),
    ]

    predictions = {
        prediction.match_id: prediction for prediction in walk_forward_surface_elo(matches)
    }

    assert predictions["d1-hard-1"].probability_a == pytest.approx(0.5)
    assert predictions["d1-hard-2"].probability_a == pytest.approx(0.5)
    assert predictions["d2-hard"].probability_a > 0.5


def test_surface_elo_skips_unknown_surface_matches():
    matches = [
        make_match(
            match_id="unknown",
            event_date=date(2026, 1, 1),
            player_a_id="a",
            player_b_id="b",
            a_won=True,
            surface="Unknown",
        ),
        make_match(
            match_id="hard",
            event_date=date(2026, 1, 2),
            player_a_id="a",
            player_b_id="b",
            a_won=True,
            surface="Hard",
        ),
    ]

    predictions = walk_forward_surface_elo(matches)

    assert [prediction.match_id for prediction in predictions] == ["hard"]
    assert predictions[0].probability_a == pytest.approx(0.5)


def test_walkovers_and_retirements_are_excluded_by_default():
    matches = [
        make_match(
            match_id="normal",
            event_date=date(2026, 1, 1),
            player_a_id="a",
            player_b_id="b",
            a_won=True,
        ),
        make_match(
            match_id="ret",
            event_date=date(2026, 1, 2),
            player_a_id="a",
            player_b_id="c",
            a_won=True,
            retirement=True,
        ),
        make_match(
            match_id="wo",
            event_date=date(2026, 1, 3),
            player_a_id="a",
            player_b_id="d",
            a_won=True,
            walkover=True,
        ),
    ]

    prediction_ids = {prediction.match_id for prediction in walk_forward_elo(matches)}
    assert prediction_ids == {"normal"}


def test_ranking_model_only_predicts_after_prior_year_training_exists():
    train_date = date(2024, 6, 1)
    matches = [
        make_match(
            match_id="t1",
            event_date=train_date,
            player_a_id="a1",
            player_b_id="b1",
            a_won=True,
            rank_a=10,
            rank_b=50,
        ),
        make_match(
            match_id="t2",
            event_date=train_date,
            player_a_id="a2",
            player_b_id="b2",
            a_won=False,
            rank_a=20,
            rank_b=40,
        ),
        make_match(
            match_id="t3",
            event_date=train_date,
            player_a_id="a3",
            player_b_id="b3",
            a_won=True,
            rank_a=5,
            rank_b=80,
        ),
        make_match(
            match_id="t4",
            event_date=train_date,
            player_a_id="a4",
            player_b_id="b4",
            a_won=False,
            rank_a=60,
            rank_b=15,
        ),
        make_match(
            match_id="future",
            event_date=date(2025, 1, 10),
            player_a_id="a5",
            player_b_id="b5",
            a_won=True,
            rank_a=8,
            rank_b=70,
        ),
    ]

    predictions = walk_forward_ranking_logit(matches, min_train_matches=4)

    assert [prediction.match_id for prediction in predictions] == ["future"]
    assert 0.0 < predictions[0].probability_a < 1.0
