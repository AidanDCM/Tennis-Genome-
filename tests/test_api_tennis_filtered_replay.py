from __future__ import annotations

import json

import pytest

from tennis_genome.research_workbench import api_tennis_filtered_replay as replay


_REQUIRED = (
    "Aces",
    "Double Faults",
    "1st serve percentage",
    "1st serve points won",
    "2nd serve points won",
    "Break Points Saved",
    "1st return points won",
    "2nd return points won",
    "Break Points Converted",
    "Service Points Won",
    "Return Points Won",
    "Total Points Won",
    "Service games won",
    "Return games won",
    "Total games won",
)


def _statistics(player_a: int, player_b: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for player_key, opponent_key, better in (
        (player_a, player_b, True),
        (player_b, player_a, False),
    ):
        service_total = 60
        service_won = 40 if better else 35
        return_total = 60
        return_won = 25 if better else 20
        values: dict[str, dict[str, object]] = {
            "Aces": {"stat_value": "5" if better else "2"},
            "Double Faults": {"stat_value": "2"},
            "1st serve percentage": {"stat_value": "65%"},
            "1st serve points won": {"stat_won": 25 if better else 22, "stat_total": 36},
            "2nd serve points won": {
                "stat_won": service_won - (25 if better else 22),
                "stat_total": 24,
            },
            "Break Points Saved": {"stat_won": 3, "stat_total": 5},
            "1st return points won": {"stat_won": 14 if better else 12, "stat_total": 36},
            "2nd return points won": {
                "stat_won": return_won - (14 if better else 12),
                "stat_total": 24,
            },
            "Break Points Converted": {"stat_won": 2, "stat_total": 5},
            "Service Points Won": {"stat_won": service_won, "stat_total": service_total},
            "Return Points Won": {"stat_won": return_won, "stat_total": return_total},
            "Total Points Won": {
                "stat_won": service_won + return_won,
                "stat_total": service_total + return_total,
            },
            "Service games won": {"stat_won": 9, "stat_total": 10},
            "Return games won": {"stat_won": 2, "stat_total": 10},
            "Total games won": {"stat_won": 11, "stat_total": 20},
        }
        assert set(values) == set(_REQUIRED)
        for name, payload in values.items():
            rows.append(
                {
                    "player_key": player_key,
                    "opponent_key": opponent_key,
                    "stat_period": "match",
                    "stat_name": name,
                    **payload,
                }
            )
    return rows


def _fixture(
    *,
    event_key: int,
    event_date: str,
    tour: str,
    player_a: int,
    player_b: int,
    winner: str = "First Player",
    status: str = "Finished",
) -> dict[str, object]:
    event_type_key = "265" if tour == "Atp Singles" else "266"
    return {
        "event_key": event_key,
        "event_date": event_date,
        "event_time": "12:00",
        "event_type_key": event_type_key,
        "event_type_type": tour,
        "event_status": status,
        "event_winner": winner,
        "event_first_player": f"P{player_a}",
        "first_player_key": player_a,
        "event_second_player": f"P{player_b}",
        "second_player_key": player_b,
        "tournament_name": "Test Open",
        "tournament_key": 999,
        "tournament_round": "Round of 16",
        "tournament_season": "2026",
        "event_qualification": "False",
        "scores": [{"score_first": "6", "score_second": "4"}],
        "pointbypoint": [{"set_number": 1, "number_game": 1}],
        "statistics": _statistics(player_a, player_b) if status == "Finished" else [],
    }


def _raw(*rows: dict[str, object]) -> bytes:
    return json.dumps({"success": 1, "result": list(rows)}).encode("utf-8")


def test_replay_builds_daily_batches_and_carries_only_prior_day_history() -> None:
    raw_atp = _raw(
        _fixture(
            event_key=1,
            event_date="2026-09-10",
            tour="Atp Singles",
            player_a=10,
            player_b=20,
        ),
        _fixture(
            event_key=2,
            event_date="2026-09-11",
            tour="Atp Singles",
            player_a=10,
            player_b=30,
        ),
    )
    raw_wta = _raw(
        _fixture(
            event_key=3,
            event_date="2026-09-10",
            tour="Wta Singles",
            player_a=40,
            player_b=50,
        )
    )

    batches = replay.build_filtered_daily_enrichment_batches(raw_atp=raw_atp, raw_wta=raw_wta)
    assert [batch.requested_date for batch in batches] == ["2026-09-10", "2026-09-11"]

    replay = replay.replay_api_tennis_filtered_shadow(raw_atp=raw_atp, raw_wta=raw_wta)
    scores = {row.event_key: row for row in replay.scores}

    assert replay.admitted_match_count == 3
    assert replay.daily_batch_count == 2
    assert scores[1].any_history is False
    assert scores[3].any_history is False
    assert scores[2].any_history is True
    assert scores[2].prior_serve_points_a == 60
    assert scores[2].prior_return_points_a == 60


def test_replay_excludes_walkover_and_tracks_source_accounting() -> None:
    raw_atp = _raw(
        _fixture(
            event_key=1,
            event_date="2026-09-10",
            tour="Atp Singles",
            player_a=10,
            player_b=20,
        ),
        _fixture(
            event_key=2,
            event_date="2026-09-10",
            tour="Atp Singles",
            player_a=30,
            player_b=40,
            status="Walk Over",
        ),
    )
    raw_wta = _raw()

    replay = replay.replay_api_tennis_filtered_shadow(raw_atp=raw_atp, raw_wta=raw_wta)

    assert replay.source_fixture_count == 2
    assert replay.admitted_match_count == 1
    assert replay.excluded_match_count == 1


def test_replay_rejects_duplicate_event_ids_across_retained_responses() -> None:
    raw_atp = _raw(
        _fixture(
            event_key=1,
            event_date="2026-09-10",
            tour="Atp Singles",
            player_a=10,
            player_b=20,
        )
    )
    raw_wta = _raw(
        _fixture(
            event_key=1,
            event_date="2026-09-10",
            tour="Wta Singles",
            player_a=30,
            player_b=40,
        )
    )

    with pytest.raises(ValueError, match="duplicate event_key"):
        replay.build_filtered_daily_enrichment_batches(raw_atp=raw_atp, raw_wta=raw_wta)


def test_replay_metrics_are_deterministic() -> None:
    raw_atp = _raw(
        _fixture(
            event_key=1,
            event_date="2026-09-10",
            tour="Atp Singles",
            player_a=10,
            player_b=20,
        ),
        _fixture(
            event_key=2,
            event_date="2026-09-11",
            tour="Atp Singles",
            player_a=10,
            player_b=30,
            winner="Second Player",
        ),
    )
    raw_wta = _raw()

    first = replay.replay_api_tennis_filtered_shadow(raw_atp=raw_atp, raw_wta=raw_wta)
    second = replay.replay_api_tennis_filtered_shadow(raw_atp=raw_atp, raw_wta=raw_wta)

    assert first.semantic_sha256 == second.semantic_sha256
    assert first.all_brier >= 0.0
    assert first.all_log_loss >= 0.0
    assert first.any_history_count == 1
