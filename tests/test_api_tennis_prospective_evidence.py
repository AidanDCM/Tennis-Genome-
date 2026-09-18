from __future__ import annotations

import json
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest

from tennis_genome.research_workbench.api_tennis_dynamic_shadow import (
    api_tennis_enrichment_to_historical_match,
)
from tennis_genome.research_workbench.api_tennis_filtered_replay import (
    build_filtered_daily_enrichment_batches,
)
from tennis_genome.research_workbench.api_tennis_prospective_evidence import (
    _target_snapshot_from_history,
    build_api_tennis_prospective_evidence,
    capture_api_tennis_prospective_evidence,
    fetch_api_tennis_wta_extension,
)

CAPTURED = datetime(2026, 9, 18, 14, 0, tzinfo=UTC)
EVENT_ID = "sr:sport_event:80000001"


def _statistics(player_a: int, player_b: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for player_key, opponent_key, service_won, return_won in (
        (player_a, player_b, 40, 25),
        (player_b, player_a, 35, 20),
    ):
        values: dict[str, dict[str, object]] = {
            "Aces": {"stat_value": "5"},
            "Double Faults": {"stat_value": "2"},
            "1st serve percentage": {"stat_value": "60%"},
            "1st serve points won": {"stat_won": 24, "stat_total": 36},
            "2nd serve points won": {"stat_won": service_won - 24, "stat_total": 24},
            "Break Points Saved": {"stat_won": 3, "stat_total": 5},
            "1st return points won": {"stat_won": 12, "stat_total": 36},
            "2nd return points won": {"stat_won": return_won - 12, "stat_total": 24},
            "Break Points Converted": {"stat_won": 2, "stat_total": 5},
            "Service Points Won": {"stat_won": service_won, "stat_total": 60},
            "Return Points Won": {"stat_won": return_won, "stat_total": 60},
            "Total Points Won": {
                "stat_won": service_won + return_won,
                "stat_total": 120,
            },
            "Service games won": {"stat_won": 9, "stat_total": 10},
            "Return games won": {"stat_won": 2, "stat_total": 10},
            "Total games won": {"stat_won": 11, "stat_total": 20},
        }
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


def _finished(
    *,
    event_key: int,
    event_date: str,
    player_a: int = 101,
    player_b: int = 202,
    name_a: str = "Alpha One",
    name_b: str = "Beta Two",
) -> dict[str, object]:
    return {
        "event_key": event_key,
        "event_date": event_date,
        "event_time": "10:00",
        "event_type_key": "266",
        "event_type_type": "Wta Singles",
        "event_status": "Finished",
        "event_winner": "First Player",
        "event_first_player": name_a,
        "first_player_key": player_a,
        "event_second_player": name_b,
        "second_player_key": player_b,
        "tournament_name": "Test Open",
        "tournament_key": 555,
        "tournament_round": "Round of 16",
        "tournament_season": "2026",
        "event_qualification": False,
        "scores": [{"score_first": "6", "score_second": "4"}],
        "pointbypoint": [{"set_number": 1, "number_game": 1}],
        "statistics": _statistics(player_a, player_b),
    }


def _target(
    *,
    event_key: int = 300,
    name_a: str = "Alpha One",
    name_b: str = "Beta Two",
    player_a: int = 101,
    player_b: int = 202,
) -> dict[str, object]:
    return {
        "event_key": event_key,
        "event_date": "2026-09-18",
        "event_time": "18:00",
        "event_type_key": "266",
        "event_type_type": "Wta Singles",
        "event_status": "Not Started",
        "event_winner": "",
        "event_first_player": name_a,
        "first_player_key": player_a,
        "event_second_player": name_b,
        "second_player_key": player_b,
        "tournament_name": "Test Open",
        "tournament_key": 555,
        "tournament_round": "Quarterfinal",
        "tournament_season": "2026",
        "event_qualification": False,
        "scores": [],
        "pointbypoint": [],
        "statistics": [],
    }


def _raw(*rows: dict[str, object]) -> bytes:
    return json.dumps({"success": 1, "result": list(rows)}).encode("utf-8")


def _dossier() -> dict[str, object]:
    return {
        "target": {
            "event_id": EVENT_ID,
            "scheduled_start": "2026-09-18T18:00:00+00:00",
            "player_a": {"id": "canon-a", "name": "Alpha One"},
            "player_b": {"id": "canon-b", "name": "Beta Two"},
        },
        "calculation": {
            "player_a_id": "canon-a",
            "player_b_id": "canon-b",
            "prediction": {
                "match_id": EVENT_ID,
                "tour": "WTA",
            },
        },
    }


def _resolution() -> dict[str, object]:
    return {
        "event_id": EVENT_ID,
        "scheduled_start": "2026-09-18T18:00:00+00:00",
    }


def _base_raw() -> bytes:
    return _raw(_finished(event_key=100, event_date="2026-09-16"))


def _extension_raw(*extra: dict[str, object]) -> bytes:
    return _raw(
        _finished(event_key=200, event_date="2026-09-17"),
        *extra,
        _target(),
    )


def test_builds_strict_prior_date_state_and_exact_direct_crosswalk() -> None:
    evidence, crosswalk, build = build_api_tennis_prospective_evidence(
        history_raw_wta=_base_raw(),
        extension_raw_wta=_extension_raw(
            _finished(event_key=250, event_date="2026-09-18", player_b=303, name_b="Gamma")
        ),
        champion_prediction_artifact_id=777,
        history_artifact_id=10531692054,
        prediction_dossier=_dossier(),
        target_resolution=_resolution(),
        captured_at=CAPTURED,
    )

    assert evidence.event_key == 300
    assert evidence.history_through_date.isoformat() == "2026-09-17"
    assert evidence.prior_serve_points_a == 120
    assert evidence.prior_return_points_a == 120
    assert evidence.prior_serve_points_b == 120
    assert evidence.prior_return_points_b == 120
    assert 0.0 < evidence.probability_a_match < 1.0
    assert evidence.historical_actual_start_admissible is False
    assert crosswalk.orientation == "DIRECT"
    assert crosswalk.mapping_basis == "EXACT_NORMALIZED_NAME_PREMATCH"
    assert build.provider_request_count == 1
    assert build.query_date_start.isoformat() == "2026-09-17"
    assert build.query_date_stop.isoformat() == "2026-09-18"
    assert "winner" not in evidence.canonical_payload()


def test_reversed_api_fixture_is_bound_without_guessing_orientation() -> None:
    reversed_target = _target(
        event_key=301,
        name_a="Beta Two",
        name_b="Alpha One",
        player_a=202,
        player_b=101,
    )
    extension = _raw(
        _finished(event_key=200, event_date="2026-09-17"),
        reversed_target,
    )
    evidence, crosswalk, _ = build_api_tennis_prospective_evidence(
        history_raw_wta=_base_raw(),
        extension_raw_wta=extension,
        champion_prediction_artifact_id=777,
        history_artifact_id=10531692054,
        prediction_dossier=_dossier(),
        target_resolution=_resolution(),
        captured_at=CAPTURED,
    )

    assert evidence.player_a_key == 202
    assert evidence.player_b_key == 101
    assert crosswalk.orientation == "REVERSED"


def test_target_sentinel_outcome_value_cannot_change_pre_match_snapshot() -> None:
    combined = _raw(
        _finished(event_key=100, event_date="2026-09-16"),
        _finished(event_key=200, event_date="2026-09-17"),
    )
    batches = build_filtered_daily_enrichment_batches(
        raw_atp=b'{"success":1,"result":[]}',
        raw_wta=combined,
    )
    records = [record for batch in batches for record in batch.admitted_records]
    history = [
        api_tennis_enrichment_to_historical_match(record, source_order=index)
        for index, record in enumerate(records)
    ]
    target = _target()

    false_snapshot = _target_snapshot_from_history(
        history_matches=history,
        target_row=target,
        sentinel_a_won=False,
    )
    true_snapshot = _target_snapshot_from_history(
        history_matches=history,
        target_row=target,
        sentinel_a_won=True,
    )

    assert false_snapshot == true_snapshot


def test_target_with_post_match_or_market_fields_fails_closed() -> None:
    leaked = _target()
    leaked["statistics"] = [{"stat_name": "Aces"}]
    with pytest.raises(ValueError, match="unexpectedly contains statistics"):
        build_api_tennis_prospective_evidence(
            history_raw_wta=_base_raw(),
            extension_raw_wta=_raw(
                _finished(event_key=200, event_date="2026-09-17"),
                leaked,
            ),
            champion_prediction_artifact_id=777,
            history_artifact_id=10531692054,
            prediction_dossier=_dossier(),
            target_resolution=_resolution(),
            captured_at=CAPTURED,
        )

    market = _target()
    market["odds"] = {"home": 1.8}
    with pytest.raises(ValueError, match="market-semantic"):
        build_api_tennis_prospective_evidence(
            history_raw_wta=_base_raw(),
            extension_raw_wta=_raw(
                _finished(event_key=200, event_date="2026-09-17"),
                market,
            ),
            champion_prediction_artifact_id=777,
            history_artifact_id=10531692054,
            prediction_dossier=_dossier(),
            target_resolution=_resolution(),
            captured_at=CAPTURED,
        )


def test_exact_name_matching_requires_one_unique_target() -> None:
    with pytest.raises(ValueError, match="found 0"):
        build_api_tennis_prospective_evidence(
            history_raw_wta=_base_raw(),
            extension_raw_wta=_raw(
                _finished(event_key=200, event_date="2026-09-17"),
                _target(name_a="Different Player"),
            ),
            champion_prediction_artifact_id=777,
            history_artifact_id=10531692054,
            prediction_dossier=_dossier(),
            target_resolution=_resolution(),
            captured_at=CAPTURED,
        )


def test_one_request_fetch_is_bounded_to_missing_history_through_target() -> None:
    seen: list[str] = []

    def provider_get(url: str) -> bytes:
        seen.append(url)
        return _extension_raw()

    extension, evidence, _, build = capture_api_tennis_prospective_evidence(
        history_raw_wta=_base_raw(),
        champion_prediction_artifact_id=777,
        history_artifact_id=10531692054,
        prediction_dossier=_dossier(),
        target_resolution=_resolution(),
        api_key="secret",
        captured_at=CAPTURED,
        provider_get=provider_get,
    )

    assert extension == _extension_raw()
    assert evidence.event_key == 300
    assert len(seen) == 1
    query = parse_qs(urlparse(seen[0]).query)
    assert query["date_start"] == ["2026-09-17"]
    assert query["date_stop"] == ["2026-09-18"]
    assert query["event_type_key"] == ["266"]
    assert query["timezone"] == ["UTC"]
    assert build.provider_request_count == 1


def test_provider_range_rejects_more_than_31_days_without_calling_provider() -> None:
    called = False

    def provider_get(_: str) -> bytes:
        nonlocal called
        called = True
        return _raw()

    with pytest.raises(ValueError, match="between one and 31 days"):
        fetch_api_tennis_wta_extension(
            date_start=datetime(2026, 8, 1, tzinfo=UTC).date(),
            date_stop=datetime(2026, 9, 18, tzinfo=UTC).date(),
            api_key="secret",
            provider_get=provider_get,
        )
    assert called is False
