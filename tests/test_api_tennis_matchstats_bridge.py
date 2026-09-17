from __future__ import annotations

import pytest

from tennis_genome.research_workbench.api_tennis_enrichment import (
    ApiTennisMatchEnrichment,
    ApiTennisPlayerMatchStats,
)
from tennis_genome.research_workbench.api_tennis_matchstats_bridge import (
    api_tennis_enrichment_to_match_stats,
)


def _player(*, player_key: int, service_total: int, return_total: int) -> ApiTennisPlayerMatchStats:
    return ApiTennisPlayerMatchStats(
        player_key=player_key,
        aces=4,
        double_faults=2,
        first_serve_pct=0.65,
        first_serve_points_won=20,
        first_serve_points_total=30,
        second_serve_points_won=8,
        second_serve_points_total=14,
        break_points_saved=3,
        break_points_faced=5,
        first_return_points_won=10,
        first_return_points_total=28,
        second_return_points_won=7,
        second_return_points_total=16,
        break_points_converted=2,
        break_point_opportunities=5,
        service_points_won=28,
        service_points_total=service_total,
        return_points_won=17,
        return_points_total=return_total,
        total_points_won=45,
        total_points_total=88,
        service_games_won=8,
        service_games_total=10,
        return_games_won=2,
        return_games_total=10,
        total_games_won=10,
        total_games_total=20,
    )


def _record() -> ApiTennisMatchEnrichment:
    return ApiTennisMatchEnrichment(
        event_key=12345,
        tour="WTA",
        event_date="2026-09-16",
        scheduled_time_utc="15:30",
        player_a_name="Player A",
        player_a_key=11,
        player_b_name="Player B",
        player_b_key=22,
        winner_side="A",
        tournament_name="Test Open",
        tournament_key=99,
        tournament_round="Round of 16",
        tournament_season="2026",
        qualification=False,
        player_a_stats=_player(player_key=11, service_total=44, return_total=46),
        player_b_stats=_player(player_key=22, service_total=46, return_total=44),
        pointbypoint_game_count=20,
        score_set_count=2,
        raw_match_sha256="a" * 64,
    )


def test_bridge_preserves_provider_counts_and_orientation() -> None:
    stats = api_tennis_enrichment_to_match_stats(_record())

    assert stats.match_id == "api-tennis:12345"
    assert stats.aces_a == 4
    assert stats.double_faults_b == 2
    assert stats.service_points_a == 44
    assert stats.service_points_b == 46
    assert stats.first_serves_in_a == 30
    assert stats.first_serve_points_won_a == 20
    assert stats.second_serve_points_won_a == 8
    assert stats.break_points_saved_a == 3
    assert stats.break_points_faced_b == 5
    assert stats.duration_minutes is None


def test_bridge_never_promotes_scheduled_time_to_duration_or_chronology() -> None:
    record = _record()
    assert record.actual_start_time_admissible is False

    stats = api_tennis_enrichment_to_match_stats(record)

    assert stats.duration_minutes is None
    assert not hasattr(stats, "scheduled_time_utc")


def test_bridge_rejects_cross_player_service_return_mismatch() -> None:
    record = _record().model_copy(
        update={
            "player_b_stats": _player(
                player_key=22,
                service_total=46,
                return_total=43,
            )
        }
    )

    with pytest.raises(ValueError, match="player A service total"):
        api_tennis_enrichment_to_match_stats(record)


def test_bridge_rejects_service_wins_above_total() -> None:
    record = _record()
    bad_a = record.player_a_stats.model_copy(
        update={
            "first_serve_points_won": 40,
            "second_serve_points_won": 10,
        }
    )
    record = record.model_copy(update={"player_a_stats": bad_a})

    with pytest.raises(ValueError, match="player A service-points-won"):
        api_tennis_enrichment_to_match_stats(record)
