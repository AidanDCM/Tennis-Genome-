from __future__ import annotations

import pytest

from tennis_genome.research_workbench.api_tennis_dynamic_shadow import (
    build_api_tennis_dynamic_shadow_batch,
)
from tennis_genome.research_workbench.api_tennis_enrichment import (
    ApiTennisEnrichmentBatch,
    ApiTennisMatchEnrichment,
    ApiTennisPlayerMatchStats,
)


def _stats(
    *,
    player_key: int,
    service_won: int,
    service_total: int = 40,
    return_won: int,
    return_total: int = 40,
) -> ApiTennisPlayerMatchStats:
    first_total = 24
    second_total = service_total - first_total
    if service_won >= 30:
        first_won = min(first_total, service_won - 10)
    else:
        first_won = min(first_total, max(0, service_won - 8))
    second_won = service_won - first_won
    if second_won < 0 or second_won > second_total:
        raise ValueError("test helper produced invalid second-serve count")

    return ApiTennisPlayerMatchStats(
        player_key=player_key,
        aces=5,
        double_faults=2,
        first_serve_pct=0.60,
        first_serve_points_won=first_won,
        first_serve_points_total=first_total,
        second_serve_points_won=second_won,
        second_serve_points_total=second_total,
        break_points_saved=3,
        break_points_faced=5,
        first_return_points_won=return_won // 2,
        first_return_points_total=24,
        second_return_points_won=return_won - return_won // 2,
        second_return_points_total=16,
        break_points_converted=2,
        break_point_opportunities=5,
        service_points_won=service_won,
        service_points_total=service_total,
        return_points_won=return_won,
        return_points_total=return_total,
        total_points_won=service_won + return_won,
        total_points_total=service_total + return_total,
        service_games_won=8,
        service_games_total=10,
        return_games_won=2,
        return_games_total=10,
        total_games_won=10,
        total_games_total=20,
    )


def _record(
    *,
    event_key: int,
    event_date: str,
    player_a_key: int,
    player_b_key: int,
    a_service_won: int,
    b_service_won: int,
    scheduled_time: str = "12:00",
) -> ApiTennisMatchEnrichment:
    return ApiTennisMatchEnrichment(
        event_key=event_key,
        tour="WTA",
        event_date=event_date,
        scheduled_time_utc=scheduled_time,
        player_a_name=f"Player {player_a_key}",
        player_a_key=player_a_key,
        player_b_name=f"Player {player_b_key}",
        player_b_key=player_b_key,
        winner_side="A",
        tournament_name="Test Open",
        tournament_key=99,
        tournament_round="Round of 16",
        tournament_season="2026",
        qualification=False,
        player_a_stats=_stats(
            player_key=player_a_key,
            service_won=a_service_won,
            return_won=40 - b_service_won,
        ),
        player_b_stats=_stats(
            player_key=player_b_key,
            service_won=b_service_won,
            return_won=40 - a_service_won,
        ),
        pointbypoint_game_count=20,
        score_set_count=2,
        raw_match_sha256=f"{event_key % 10}" * 64,
    )


def _batch(*records: ApiTennisMatchEnrichment, requested_date: str) -> ApiTennisEnrichmentBatch:
    return ApiTennisEnrichmentBatch(
        requested_date=requested_date,
        raw_response_sha256="a" * 64,
        admitted_records=records,
        exclusion_counts=(),
    )


def test_dynamic_shadow_blocks_same_day_update_but_uses_prior_days() -> None:
    first = _record(
        event_key=100,
        event_date="2026-09-15",
        player_a_key=1,
        player_b_key=2,
        a_service_won=34,
        b_service_won=20,
        scheduled_time="09:00",
    )
    second_same_day = _record(
        event_key=101,
        event_date="2026-09-15",
        player_a_key=1,
        player_b_key=3,
        a_service_won=34,
        b_service_won=20,
        scheduled_time="22:00",
    )
    next_day = _record(
        event_key=102,
        event_date="2026-09-16",
        player_a_key=1,
        player_b_key=4,
        a_service_won=30,
        b_service_won=24,
    )

    result = build_api_tennis_dynamic_shadow_batch(
        [
            _batch(first, second_same_day, requested_date="2026-09-15"),
            _batch(next_day, requested_date="2026-09-16"),
        ]
    )
    by_event = {record.event_key: record for record in result.records}

    assert by_event[100].prior_serve_points_a == 0
    assert by_event[101].prior_serve_points_a == 0
    assert by_event[100].prior_return_points_a == 0
    assert by_event[101].prior_return_points_a == 0
    assert by_event[102].prior_serve_points_a == 80
    assert by_event[102].prior_return_points_a == 80
    assert by_event[102].probability_a_match > 0.5


def test_dynamic_shadow_ignores_scheduled_clock_for_same_day_state() -> None:
    early = _record(
        event_key=200,
        event_date="2026-09-15",
        player_a_key=1,
        player_b_key=2,
        a_service_won=34,
        b_service_won=20,
        scheduled_time="00:01",
    )
    late = _record(
        event_key=201,
        event_date="2026-09-15",
        player_a_key=1,
        player_b_key=3,
        a_service_won=34,
        b_service_won=20,
        scheduled_time="23:59",
    )

    result = build_api_tennis_dynamic_shadow_batch(
        [_batch(late, early, requested_date="2026-09-15")]
    )
    by_event = {record.event_key: record for record in result.records}

    assert by_event[200].prior_serve_points_a == 0
    assert by_event[201].prior_serve_points_a == 0
    assert by_event[200].probability_a_match == pytest.approx(0.5)
    assert by_event[201].probability_a_match == pytest.approx(0.5)


def test_dynamic_shadow_is_deterministic_across_batch_order() -> None:
    day_one = _record(
        event_key=300,
        event_date="2026-09-15",
        player_a_key=1,
        player_b_key=2,
        a_service_won=32,
        b_service_won=22,
    )
    day_two = _record(
        event_key=301,
        event_date="2026-09-16",
        player_a_key=1,
        player_b_key=3,
        a_service_won=30,
        b_service_won=24,
    )
    first_batch = _batch(day_one, requested_date="2026-09-15")
    second_batch = _batch(day_two, requested_date="2026-09-16")

    forward = build_api_tennis_dynamic_shadow_batch([first_batch, second_batch])
    reverse = build_api_tennis_dynamic_shadow_batch([second_batch, first_batch])

    assert forward.semantic_sha256 == reverse.semantic_sha256


def test_dynamic_shadow_rejects_conflicting_duplicate_event() -> None:
    original = _record(
        event_key=400,
        event_date="2026-09-15",
        player_a_key=1,
        player_b_key=2,
        a_service_won=32,
        b_service_won=22,
    )
    changed = original.model_copy(
        update={
            "raw_match_sha256": "f" * 64,
            "player_a_stats": _stats(
                player_key=1,
                service_won=30,
                return_won=18,
            ),
        }
    )

    with pytest.raises(ValueError, match="conflicting API-Tennis event_key"):
        build_api_tennis_dynamic_shadow_batch(
            [
                _batch(original, requested_date="2026-09-15"),
                _batch(changed, requested_date="2026-09-15"),
            ]
        )
