from __future__ import annotations

from datetime import date
from math import sqrt

import pytest

from tennis_genome.data.canonical import (
    HistoricalMatch,
    MatchOutcome,
    MatchStats,
    PreMatchState,
)
from tennis_genome.ratings.dynamic_serve_return import (
    DynamicServeReturnConfig,
    walk_forward_dynamic_serve_return,
)


def _match(
    *,
    match_id: str,
    event_date: date,
    player_a: str,
    player_b: str,
    a_service_won: int | None = None,
    a_service_total: int | None = None,
    b_service_won: int | None = None,
    b_service_total: int | None = None,
) -> HistoricalMatch:
    pre_match = PreMatchState(
        match_id=match_id,
        tour="ATP",
        event_date=event_date,
        source_order=0,
        tournament_id="test-event",
        tournament_name="Test Event",
        tournament_level="A",
        surface="Hard",
        round="R32",
        best_of=3,
        player_a_id=player_a,
        player_b_id=player_b,
        player_a_name=player_a,
        player_b_name=player_b,
        rank_a=None,
        rank_b=None,
        rank_points_a=None,
        rank_points_b=None,
    )
    outcome = MatchOutcome(
        match_id=match_id,
        a_won=True,
        score="6-4 6-4",
        retirement=False,
        walkover=False,
    )
    stats = None
    if a_service_total is not None or b_service_total is not None:
        a_first = None if a_service_won is None else a_service_won
        b_first = None if b_service_won is None else b_service_won
        stats = MatchStats(
            match_id=match_id,
            service_points_a=a_service_total,
            service_points_b=b_service_total,
            first_serve_points_won_a=a_first,
            first_serve_points_won_b=b_first,
            second_serve_points_won_a=0 if a_first is not None else None,
            second_serve_points_won_b=0 if b_first is not None else None,
        )
    return HistoricalMatch(pre_match=pre_match, outcome=outcome, stats=stats)


def _snapshot_map(matches: list[HistoricalMatch]):
    return {
        snapshot.match_id: snapshot
        for snapshot in walk_forward_dynamic_serve_return(matches)
    }


def test_same_day_targets_are_frozen_before_any_same_day_update() -> None:
    day = date(2026, 1, 1)
    matches = [
        _match(
            match_id="m1",
            event_date=day,
            player_a="A",
            player_b="B",
            a_service_won=45,
            a_service_total=60,
            b_service_won=35,
            b_service_total=60,
        ),
        _match(
            match_id="m2",
            event_date=day,
            player_a="A",
            player_b="C",
            a_service_won=40,
            a_service_total=60,
            b_service_won=38,
            b_service_total=60,
        ),
    ]

    snapshots = _snapshot_map(matches)

    assert snapshots["m1"].serve_mean_a == 0.0
    assert snapshots["m2"].serve_mean_a == 0.0
    assert snapshots["m1"].prior_serve_points_a == 0
    assert snapshots["m2"].prior_serve_points_a == 0
    assert snapshots["m1"].serve_sd_a == pytest.approx(sqrt(0.50))
    assert snapshots["m2"].serve_sd_a == pytest.approx(sqrt(0.50))


def test_next_day_state_is_invariant_to_arbitrary_same_day_match_order() -> None:
    day1 = date(2026, 1, 1)
    day2 = date(2026, 1, 2)
    ab_first = [
        _match(
            match_id="m1",
            event_date=day1,
            player_a="A",
            player_b="B",
            a_service_won=50,
            a_service_total=60,
            b_service_won=30,
            b_service_total=60,
        ),
        _match(
            match_id="m2",
            event_date=day1,
            player_a="A",
            player_b="C",
            a_service_won=30,
            a_service_total=60,
            b_service_won=45,
            b_service_total=60,
        ),
        _match(match_id="m3", event_date=day2, player_a="A", player_b="D"),
    ]
    ac_first = [
        _match(
            match_id="m2",
            event_date=day1,
            player_a="A",
            player_b="B",
            a_service_won=50,
            a_service_total=60,
            b_service_won=30,
            b_service_total=60,
        ),
        _match(
            match_id="m1",
            event_date=day1,
            player_a="A",
            player_b="C",
            a_service_won=30,
            a_service_total=60,
            b_service_won=45,
            b_service_total=60,
        ),
        _match(match_id="m3", event_date=day2, player_a="A", player_b="D"),
    ]

    first = _snapshot_map(ab_first)["m3"]
    second = _snapshot_map(ac_first)["m3"]

    assert first.serve_mean_a == pytest.approx(second.serve_mean_a)
    assert first.return_mean_a == pytest.approx(second.return_mean_a)
    assert first.serve_sd_a == pytest.approx(second.serve_sd_a)
    assert first.return_sd_a == pytest.approx(second.return_sd_a)
    assert first.probability_a_serve_point == pytest.approx(
        second.probability_a_serve_point
    )


def test_uncertainty_shrinks_with_points_and_grows_after_layoff() -> None:
    config = DynamicServeReturnConfig(
        process_variance_per_day=0.002,
        mean_reversion_half_life_days=180.0,
    )
    matches = [
        _match(
            match_id="m1",
            event_date=date(2026, 1, 1),
            player_a="A",
            player_b="B",
            a_service_won=48,
            a_service_total=70,
            b_service_won=36,
            b_service_total=70,
        ),
        _match(
            match_id="m2",
            event_date=date(2026, 1, 2),
            player_a="A",
            player_b="C",
        ),
        _match(
            match_id="m3",
            event_date=date(2026, 5, 1),
            player_a="A",
            player_b="D",
        ),
    ]

    snapshots = {
        snapshot.match_id: snapshot
        for snapshot in walk_forward_dynamic_serve_return(matches, config=config)
    }

    initial_sd = snapshots["m1"].serve_sd_a
    informed_sd = snapshots["m2"].serve_sd_a
    layoff_sd = snapshots["m3"].serve_sd_a

    assert informed_sd < initial_sd
    assert layoff_sd > informed_sd
    assert abs(snapshots["m3"].serve_mean_a) < abs(snapshots["m2"].serve_mean_a)


def test_opponent_return_state_changes_new_servers_expected_point_rate() -> None:
    matches = [
        _match(
            match_id="m1",
            event_date=date(2026, 1, 1),
            player_a="X",
            player_b="B",
            a_service_won=15,
            a_service_total=60,
            b_service_won=37,
            b_service_total=60,
        ),
        _match(
            match_id="m2",
            event_date=date(2026, 1, 2),
            player_a="D",
            player_b="B",
        ),
    ]

    snapshot = _snapshot_map(matches)["m2"]

    assert snapshot.return_mean_b > 0.0
    assert snapshot.probability_a_serve_point < 0.62


def test_information_depth_is_retained_as_separate_uncertainty_context() -> None:
    matches = [
        _match(
            match_id="m1",
            event_date=date(2026, 1, 1),
            player_a="A",
            player_b="B",
            a_service_won=40,
            a_service_total=60,
            b_service_won=38,
            b_service_total=60,
        ),
        _match(
            match_id="m2",
            event_date=date(2026, 1, 2),
            player_a="A",
            player_b="B",
        ),
    ]

    snapshot = _snapshot_map(matches)["m2"]

    assert snapshot.prior_serve_points_a == 60
    assert snapshot.prior_return_points_a == 60
    assert snapshot.prior_serve_points_b == 60
    assert snapshot.prior_return_points_b == 60
    assert snapshot.a_serve_logit_sd > 0.0
    assert snapshot.b_serve_logit_sd > 0.0


def test_dynamic_config_rejects_overconfident_or_invalid_operating_points() -> None:
    with pytest.raises(ValueError, match="point_information_weight"):
        DynamicServeReturnConfig(point_information_weight=0.0)
    with pytest.raises(ValueError, match="min_variance"):
        DynamicServeReturnConfig(min_variance=0.60)
    with pytest.raises(ValueError, match="max_variance"):
        DynamicServeReturnConfig(max_variance=0.10)
