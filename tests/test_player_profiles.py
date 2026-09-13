from __future__ import annotations

from dataclasses import replace
from datetime import date
from math import log, log1p

import pytest

from tennis_genome.data.canonical import (
    HistoricalMatch,
    MatchOutcome,
    MatchStats,
    PreMatchState,
    Tour,
)
from tennis_genome.features.foundational import walk_forward_foundational_features
from tennis_genome.profiles.spec import (
    conditional_profile_fields,
    core_profile_fields,
    field_role,
)
from tennis_genome.profiles.state import walk_forward_player_profiles
from tennis_genome.ratings.elo import expected_score


def _match(
    *,
    match_id: str,
    event_date: date,
    player_a_id: str,
    player_b_id: str,
    a_won: bool,
    tour: Tour = "ATP",
    duration: int | None = None,
    service_points_a: int | None = None,
    service_points_b: int | None = None,
    first_serve_points_won_a: int | None = None,
    first_serve_points_won_b: int | None = None,
    second_serve_points_won_a: int | None = None,
    second_serve_points_won_b: int | None = None,
    rank_a: int | None = None,
    rank_b: int | None = None,
    age_a: float | None = None,
    age_b: float | None = None,
    height_a: int | None = None,
    height_b: int | None = None,
    hand_a: str | None = None,
    hand_b: str | None = None,
) -> HistoricalMatch:
    pre_match = PreMatchState(
        match_id=match_id,
        tour=tour,
        event_date=event_date,
        source_order=0,
        tournament_id="test-event",
        tournament_name="Test Event",
        tournament_level="A",
        surface="Hard",
        round="R32",
        best_of=3,
        player_a_id=player_a_id,
        player_b_id=player_b_id,
        player_a_name=player_a_id,
        player_b_name=player_b_id,
        rank_a=rank_a,
        rank_b=rank_b,
        rank_points_a=None,
        rank_points_b=None,
        hand_a=hand_a,
        hand_b=hand_b,
        height_cm_a=height_a,
        height_cm_b=height_b,
        age_years_a=age_a,
        age_years_b=age_b,
    )
    outcome = MatchOutcome(
        match_id=match_id,
        a_won=a_won,
        score=None,
        retirement=False,
        walkover=False,
    )
    stats = None
    if any(
        value is not None
        for value in (
            duration,
            service_points_a,
            service_points_b,
            first_serve_points_won_a,
            first_serve_points_won_b,
            second_serve_points_won_a,
            second_serve_points_won_b,
        )
    ):
        stats = MatchStats(
            match_id=match_id,
            service_points_a=service_points_a,
            service_points_b=service_points_b,
            first_serve_points_won_a=first_serve_points_won_a,
            first_serve_points_won_b=first_serve_points_won_b,
            second_serve_points_won_a=second_serve_points_won_a,
            second_serve_points_won_b=second_serve_points_won_b,
            duration_minutes=duration,
        )
    return HistoricalMatch(pre_match=pre_match, outcome=outcome, stats=stats)


def _logit(probability: float) -> float:
    return log(probability / (1.0 - probability))


def test_same_date_profiles_freeze_before_all_current_date_results():
    matches = [
        _match(
            match_id="d1-a-b",
            event_date=date(2025, 1, 1),
            player_a_id="a",
            player_b_id="b",
            a_won=True,
            duration=60,
        ),
        _match(
            match_id="d1-a-c",
            event_date=date(2025, 1, 1),
            player_a_id="a",
            player_b_id="c",
            a_won=True,
            duration=90,
        ),
        _match(
            match_id="d2-a-d",
            event_date=date(2025, 1, 2),
            player_a_id="a",
            player_b_id="d",
            a_won=True,
            duration=70,
        ),
    ]

    pairs = {pair.match_id: pair for pair in walk_forward_player_profiles(matches)}
    first = pairs["d1-a-b"].player_a
    second = pairs["d1-a-c"].player_a
    next_day = pairs["d2-a-d"].player_a

    assert first.elo_rating == pytest.approx(second.elo_rating)
    assert first.prior_matches == second.prior_matches == 0
    assert first.form_result_30 == pytest.approx(second.form_result_30)
    assert first.minutes_14 == pytest.approx(second.minutes_14)

    assert next_day.elo_rating > first.elo_rating
    assert next_day.prior_matches == 2
    assert next_day.event_gap_days == pytest.approx(1.0)
    assert next_day.matches_14 == 2
    assert next_day.minutes_14 == pytest.approx(150.0)
    assert next_day.previous_event_minutes == 150


def test_future_append_does_not_change_existing_profile_hashes():
    history = [
        _match(
            match_id="m1",
            event_date=date(2025, 1, 1),
            player_a_id="a",
            player_b_id="b",
            a_won=True,
            duration=70,
        ),
        _match(
            match_id="m2",
            event_date=date(2025, 1, 5),
            player_a_id="a",
            player_b_id="c",
            a_won=False,
            duration=80,
        ),
        _match(
            match_id="m3",
            event_date=date(2025, 1, 9),
            player_a_id="b",
            player_b_id="c",
            a_won=True,
            duration=65,
        ),
    ]
    future = _match(
        match_id="future",
        event_date=date(2025, 2, 1),
        player_a_id="a",
        player_b_id="b",
        a_won=False,
        duration=75,
    )

    before = {
        pair.match_id: (pair.player_a.profile_hash, pair.player_b.profile_hash)
        for pair in walk_forward_player_profiles(history)
    }
    after = {
        pair.match_id: (pair.player_a.profile_hash, pair.player_b.profile_hash)
        for pair in walk_forward_player_profiles([*history, future])
        if pair.match_id in before
    }

    assert after == before


def test_profile_differences_match_existing_foundational_state():
    matches = [
        _match(
            match_id="m1",
            event_date=date(2025, 1, 1),
            player_a_id="a",
            player_b_id="b",
            a_won=True,
            duration=80,
            service_points_a=60,
            service_points_b=58,
            first_serve_points_won_a=28,
            first_serve_points_won_b=24,
            second_serve_points_won_a=12,
            second_serve_points_won_b=11,
            age_a=25.0,
            age_b=30.0,
            height_a=188,
            height_b=180,
        ),
        _match(
            match_id="m2",
            event_date=date(2025, 1, 8),
            player_a_id="a",
            player_b_id="c",
            a_won=False,
            duration=100,
            service_points_a=65,
            service_points_b=62,
            first_serve_points_won_a=27,
            first_serve_points_won_b=30,
            second_serve_points_won_a=10,
            second_serve_points_won_b=13,
            age_a=25.0,
            age_b=27.0,
            height_a=188,
            height_b=185,
        ),
        _match(
            match_id="target",
            event_date=date(2025, 1, 12),
            player_a_id="a",
            player_b_id="b",
            a_won=True,
            duration=75,
            service_points_a=55,
            service_points_b=57,
            first_serve_points_won_a=26,
            first_serve_points_won_b=25,
            second_serve_points_won_a=11,
            second_serve_points_won_b=10,
            age_a=25.0,
            age_b=30.0,
            height_a=188,
            height_b=180,
        ),
    ]

    profile = {pair.match_id: pair for pair in walk_forward_player_profiles(matches)}["target"]
    foundational = {
        snapshot.match_id: snapshot for snapshot in walk_forward_foundational_features(matches)
    }["target"]
    a = profile.player_a
    b = profile.player_b

    p_a = expected_score(a.elo_rating, b.elo_rating)
    assert foundational.elo_logit == pytest.approx(_logit(p_a))
    assert foundational.serve_rating_diff == pytest.approx(a.serve_rating - b.serve_rating)
    assert foundational.return_rating_diff == pytest.approx(a.return_rating - b.return_rating)
    assert foundational.form_result_30_diff == pytest.approx(a.form_result_30 - b.form_result_30)
    assert foundational.form_result_90_diff == pytest.approx(a.form_result_90 - b.form_result_90)
    assert foundational.form_point_30_diff == pytest.approx(a.form_point_30 - b.form_point_30)
    assert foundational.form_point_90_diff == pytest.approx(a.form_point_90 - b.form_point_90)
    assert foundational.event_gap_days_diff == pytest.approx(a.event_gap_days - b.event_gap_days)
    assert foundational.minutes_7_diff == pytest.approx(log1p(a.minutes_7) - log1p(b.minutes_7))
    assert foundational.minutes_14_diff == pytest.approx(log1p(a.minutes_14) - log1p(b.minutes_14))
    assert foundational.minutes_28_diff == pytest.approx(log1p(a.minutes_28) - log1p(b.minutes_28))
    assert foundational.matches_14_diff == pytest.approx(a.matches_14 - b.matches_14)
    assert foundational.matches_28_diff == pytest.approx(a.matches_28 - b.matches_28)
    assert foundational.previous_event_minutes_diff == pytest.approx(
        log1p(a.previous_event_minutes) - log1p(b.previous_event_minutes)
    )
    assert foundational.age_diff == pytest.approx(a.age_years - b.age_years)
    assert foundational.height_diff == pytest.approx(a.height_cm - b.height_cm)


def test_profile_hash_is_deterministic_and_content_addressed():
    pair = walk_forward_player_profiles(
        [
            _match(
                match_id="m1",
                event_date=date(2025, 1, 1),
                player_a_id="a",
                player_b_id="b",
                a_won=True,
                rank_a=10,
                rank_b=20,
            )
        ]
    )[0]
    profile = pair.player_a

    assert profile.profile_hash == profile.profile_hash
    assert replace(profile, ranking=11).profile_hash != profile.profile_hash


def test_profile_permissions_block_rejected_and_demoted_fields():
    atp_core = core_profile_fields("ATP")
    wta_core = core_profile_fields("WTA")

    assert "elo_rating" in atp_core
    assert "elo_rating" in wta_core
    assert "serve_rating" in atp_core
    assert "serve_rating" not in wta_core
    assert "serve_rating" in conditional_profile_fields("WTA")
    assert field_role("age_years", "ATP") == "core"
    assert field_role("age_years", "WTA") == "descriptive"
    assert field_role("hand", "ATP") == "descriptive"
    assert field_role("hand", "WTA") == "descriptive"
