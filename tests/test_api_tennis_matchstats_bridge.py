from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tennis_genome.research_workbench.api_tennis_enrichment import (
    ApiTennisMatchEnrichment,
    ApiTennisPlayerMatchStats,
)
from tennis_genome.research_workbench.api_tennis_history_bridge import (
    build_candidate_historical_match,
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
        second_serve_points_total=service_total - 30,
        break_points_saved=3,
        break_points_faced=5,
        first_return_points_won=10,
        first_return_points_total=30,
        second_return_points_won=return_total - 30 - 8,
        second_return_points_total=return_total - 30,
        break_points_converted=2,
        break_point_opportunities=5,
        service_points_won=28,
        service_points_total=service_total,
        return_points_won=return_total - 28,
        return_points_total=return_total,
        total_points_won=return_total,
        total_points_total=service_total + return_total,
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


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"service_points_won": 27}, "A_SERVICE_WINS_SPLIT_MISMATCH"),
        ({"first_serve_points_total": 31}, "A_SERVICE_TOTAL_SPLIT_MISMATCH"),
        ({"total_points_won": 1}, "A_TOTAL_POINTS_WINS_MISMATCH"),
        # Aggregate service wins stay at 28; opponent split counts expose the conflict.
        (
            {"first_serve_points_won": 19, "second_serve_points_won": 9},
            "A_FIRST_SERVE_RETURN_WINS_MISMATCH",
        ),
    ],
)
def test_bridge_rejects_incompatible_provider_point_fields(updates, reason) -> None:
    record = _record()
    invalid = record.model_copy(
        update={"player_a_stats": record.player_a_stats.model_copy(update=updates)}
    )
    with pytest.raises(ValueError, match=reason):
        api_tennis_enrichment_to_match_stats(invalid)


def _candidate(**updates):
    options = {
        "reviewed_player_ids": {11: "wta:id:900", 22: "wta:id:100"},
        "reviewed_surface": "Hard",
        "reviewed_tournament_level": "I",
        "source_observed_at": datetime(2026, 9, 17, tzinfo=UTC),
        "target_cutoff_at": datetime(2026, 9, 18, tzinfo=UTC),
        "source_manifest_sha256": "b" * 64,
    }
    options.update(updates)
    return build_candidate_historical_match(_record(), **options)


def test_candidate_history_requires_explicit_context_and_reorients_every_field() -> None:
    evidence = _candidate()
    match = evidence.match

    assert match.pre_match.player_a_id == "wta:id:100"
    assert match.pre_match.player_b_id == "wta:id:900"
    assert match.pre_match.surface == "Hard"
    assert match.outcome.a_won is False
    assert match.stats is not None
    assert match.stats.service_points_a == 46
    assert match.stats.service_points_b == 44
    assert match.stats.first_serve_points_won_a == 20
    assert match.stats.first_serve_points_won_b == 20
    assert match.stats.duration_minutes is None
    assert evidence.raw_match_sha256 == "a" * 64


def test_candidate_history_rejects_unknown_surface_and_missing_identity() -> None:
    with pytest.raises(ValueError, match="surface"):
        _candidate(reviewed_surface="Unknown")
    with pytest.raises(ValueError, match="crosswalks"):
        _candidate(reviewed_player_ids={11: "wta:id:900"})


def test_candidate_history_rejects_late_or_same_date_evidence() -> None:
    with pytest.raises(ValueError, match="observed before"):
        _candidate(source_observed_at=datetime(2026, 9, 18, tzinfo=UTC))
    with pytest.raises(ValueError, match="finished match before"):
        _candidate(source_observed_at=datetime(2026, 9, 15, tzinfo=UTC))
    with pytest.raises(ValueError, match="precede target"):
        build_candidate_historical_match(
            _record().model_copy(update={"event_date": "2026-09-18"}),
            reviewed_player_ids={11: "wta:id:900", 22: "wta:id:100"},
            reviewed_surface="Hard",
            reviewed_tournament_level="I",
            source_observed_at=datetime(2026, 9, 18, tzinfo=UTC),
            target_cutoff_at=datetime(2026, 9, 18, 12, tzinfo=UTC),
            source_manifest_sha256="b" * 64,
        )
