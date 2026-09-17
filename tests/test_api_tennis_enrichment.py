from __future__ import annotations

import json

import pytest

from tennis_genome.research_workbench.api_tennis_enrichment import (
    build_api_tennis_enrichment_batch,
    parse_api_tennis_match_enrichment,
)


def _ratio(player_key: int, name: str, won: int, total: int) -> dict[str, object]:
    return {
        "player_key": player_key,
        "stat_period": "match",
        "stat_type": "Points",
        "stat_name": name,
        "stat_value": f"{round(100 * won / total) if total else 0}%",
        "stat_won": won,
        "stat_total": total,
    }


def _plain(player_key: int, name: str, value: int) -> dict[str, object]:
    return {
        "player_key": player_key,
        "stat_period": "match",
        "stat_type": "Service",
        "stat_name": name,
        "stat_value": str(value),
        "stat_won": None,
        "stat_total": None,
    }


def _stats(player_key: int, *, strong: bool) -> list[dict[str, object]]:
    if strong:
        first_serve = (24, 30)
        second_serve = (8, 14)
        bp_saved = (3, 4)
        first_return = (12, 25)
        second_return = (8, 16)
        bp_converted = (4, 7)
        service_points = (32, 44)
        return_points = (20, 41)
        total_points = (52, 85)
        service_games = (8, 9)
        return_games = (4, 9)
        total_games = (12, 18)
        first_serve_pct = "68%"
        aces = 5
        dfs = 2
    else:
        first_serve = (13, 25)
        second_serve = (8, 16)
        bp_saved = (3, 7)
        first_return = (6, 30)
        second_return = (6, 14)
        bp_converted = (1, 4)
        service_points = (21, 41)
        return_points = (12, 44)
        total_points = (33, 85)
        service_games = (5, 9)
        return_games = (1, 9)
        total_games = (6, 18)
        first_serve_pct = "61%"
        aces = 1
        dfs = 4

    rows = [
        _plain(player_key, "Aces", aces),
        _plain(player_key, "Double Faults", dfs),
        {
            "player_key": player_key,
            "stat_period": "match",
            "stat_type": "Service",
            "stat_name": "1st serve percentage",
            "stat_value": first_serve_pct,
            "stat_won": None,
            "stat_total": None,
        },
    ]
    for name, pair in (
        ("1st serve points won", first_serve),
        ("2nd serve points won", second_serve),
        ("Break Points Saved", bp_saved),
        ("1st return points won", first_return),
        ("2nd return points won", second_return),
        ("Break Points Converted", bp_converted),
        ("Service Points Won", service_points),
        ("Return Points Won", return_points),
        ("Total Points Won", total_points),
        ("Service games won", service_games),
        ("Return games won", return_games),
        ("Total games won", total_games),
    ):
        rows.append(_ratio(player_key, name, *pair))
    return rows


def _finished_row(*, event_key: int = 101, date: str = "2026-09-16") -> dict[str, object]:
    return {
        "event_key": event_key,
        "event_date": date,
        "event_time": "15:30",
        "event_first_player": "Player A",
        "first_player_key": 11,
        "event_second_player": "Player B",
        "second_player_key": 22,
        "event_final_result": "2 - 0",
        "event_status": "Finished",
        "event_type_type": "Wta Singles",
        "event_winner": "First Player",
        "event_qualification": "False",
        "tournament_key": 999,
        "tournament_name": "Test Open",
        "tournament_round": "Round of 16",
        "tournament_season": "2026",
        "statistics": _stats(11, strong=True) + _stats(22, strong=False),
        "pointbypoint": [
            {
                "set_number": "Set 1",
                "number_game": "1",
                "player_served": "First Player",
                "points": [{"number_point": "1", "score": "15 - 0"}],
            }
        ],
        "scores": [{"score_first": "6", "score_second": "3"}],
    }


def _payload(rows: list[dict[str, object]]) -> bytes:
    return json.dumps({"success": 1, "result": rows}, sort_keys=True).encode()


def test_finished_match_preserves_orientation_and_scheduled_time_semantics() -> None:
    record = parse_api_tennis_match_enrichment(_finished_row())

    assert record.tour == "WTA"
    assert record.player_a_key == 11
    assert record.player_b_key == 22
    assert record.winner_side == "A"
    assert record.scheduled_time_utc == "15:30"
    assert record.actual_start_time_admissible is False
    assert record.qualification is False
    assert record.player_a_stats.first_serve_points_won == 24
    assert record.player_a_stats.first_serve_points_total == 30
    assert record.player_b_stats.double_faults == 4
    assert record.pointbypoint_game_count == 1


def test_string_true_qualification_is_parsed_without_python_truthiness_bug() -> None:
    row = _finished_row()
    row["event_qualification"] = "True"

    assert parse_api_tennis_match_enrichment(row).qualification is True


def test_batch_excludes_cancelled_walkover_retired_and_non_main_tour() -> None:
    finished = _finished_row(event_key=1)
    cancelled = _finished_row(event_key=2)
    cancelled["event_status"] = "Cancelled"
    walkover = _finished_row(event_key=3)
    walkover["event_status"] = "Walk Over"
    retired = _finished_row(event_key=4)
    retired["event_status"] = "Retired"
    challenger = _finished_row(event_key=5)
    challenger["event_type_type"] = "Challenger Men Singles"

    batch = build_api_tennis_enrichment_batch(
        _payload([finished, cancelled, walkover, retired, challenger]),
        requested_date="2026-09-16",
    )

    assert [row.event_key for row in batch.admitted_records] == [1]
    assert dict(batch.exclusion_counts) == {
        "CANCELLED": 1,
        "NOT_MAIN_TOUR_SINGLES": 1,
        "RETIRED": 1,
        "WALK_OVER": 1,
    }


def test_missing_required_statistics_fail_closed_into_exclusion() -> None:
    row = _finished_row()
    row["statistics"] = [
        stat for stat in row["statistics"] if stat["stat_name"] != "2nd serve points won"
    ]

    batch = build_api_tennis_enrichment_batch(
        _payload([row]), requested_date="2026-09-16"
    )

    assert batch.admitted_records == ()
    assert dict(batch.exclusion_counts) == {"MISSING_OR_INVALID_ENRICHMENT": 1}


def test_date_mismatch_is_not_silently_reused() -> None:
    row = _finished_row(date="2026-09-15")

    batch = build_api_tennis_enrichment_batch(
        _payload([row]), requested_date="2026-09-16"
    )

    assert batch.admitted_records == ()
    assert dict(batch.exclusion_counts) == {"DATE_MISMATCH": 1}


def test_duplicate_event_keys_fail_closed() -> None:
    row = _finished_row(event_key=700)

    with pytest.raises(ValueError, match="duplicate API-Tennis event_key"):
        build_api_tennis_enrichment_batch(
            _payload([row, row]), requested_date="2026-09-16"
        )


def test_invalid_won_total_pair_is_excluded() -> None:
    row = _finished_row()
    for stat in row["statistics"]:
        if stat["player_key"] == 11 and stat["stat_name"] == "Service Points Won":
            stat["stat_won"] = 45
            stat["stat_total"] = 44
            break

    batch = build_api_tennis_enrichment_batch(
        _payload([row]), requested_date="2026-09-16"
    )

    assert batch.admitted_records == ()
    assert dict(batch.exclusion_counts) == {"MISSING_OR_INVALID_ENRICHMENT": 1}
