from __future__ import annotations

import json
from pathlib import Path

import pytest

from tennis_genome.research_workbench.api_tennis_source_audit import (
    capture_api_tennis_source_probe,
    inspect_fixture_payload,
)


def _payload() -> bytes:
    return json.dumps(
        {
            "success": 1,
            "result": [
                {
                    "event_key": "1",
                    "event_date": "2026-09-16",
                    "event_time": "14:00",
                    "event_first_player": "A",
                    "event_second_player": "B",
                    "event_status": "Finished",
                    "event_type_type": "Atp Singles",
                    "pointbypoint": [
                        {
                            "set_number": "Set 1",
                            "number_game": "1",
                            "points": [{"number_point": "1", "score": "15 - 0"}],
                        }
                    ],
                    "scores": [{"score_first": "6", "score_second": "4"}],
                    "statistics": [{"stat_name": "Aces", "stat_value": "5"}],
                },
                {
                    "event_key": "2",
                    "event_date": "2026-09-16",
                    "event_time": "16:30",
                    "event_first_player": "C",
                    "event_second_player": "D",
                    "event_status": "Finished",
                    "event_type_type": "Wta Singles",
                    "pointbypoint": [],
                    "scores": [{"score_first": "7", "score_second": "5"}],
                    "statistics": [],
                },
            ],
        },
        separators=(",", ":"),
    ).encode()


def test_fixture_probe_classifies_scheduled_time_as_not_actual_start() -> None:
    audit = inspect_fixture_payload(_payload(), requested_date="2026-09-16")
    assert audit.provider_request_count == 1
    assert audit.fixture_count == 2
    assert audit.atp_singles_count == 1
    assert audit.wta_singles_count == 1
    assert audit.finished_count == 2
    assert audit.pointbypoint_nonempty_count == 1
    assert audit.statistics_nonempty_count == 1
    assert audit.scores_nonempty_count == 2
    assert "$.result[0].event_time" in audit.timestamp_like_paths
    assert audit.separate_actual_start_field_paths == ()
    assert audit.historical_actual_start_admissible is False
    assert "HISTORICAL_ACTUAL_START_CHRONOLOGY" in audit.excluded_research_roles


def test_probe_uses_exactly_one_provider_request_and_retains_bytes(tmp_path: Path) -> None:
    calls: list[str] = []

    def provider_get(url: str) -> bytes:
        calls.append(url)
        return _payload()

    audit = capture_api_tennis_source_probe(
        requested_date="2026-09-16",
        api_key="secret-value",
        output_dir=tmp_path / "out",
        provider_get=provider_get,
    )
    assert len(calls) == 1
    assert "method=get_fixtures" in calls[0]
    assert "date_start=2026-09-16" in calls[0]
    assert "date_stop=2026-09-16" in calls[0]
    assert audit.provider_request_count == 1
    assert (tmp_path / "out" / "raw-fixtures.json").read_bytes() == _payload()
    assert "secret-value" not in (tmp_path / "out" / "manifest.json").read_text()


def test_probe_rejects_empty_api_key_before_provider_call(tmp_path: Path) -> None:
    called = False

    def provider_get(_url: str) -> bytes:
        nonlocal called
        called = True
        return _payload()

    with pytest.raises(ValueError, match="API_TENNIS_API must be configured"):
        capture_api_tennis_source_probe(
            requested_date="2026-09-16",
            api_key="",
            output_dir=tmp_path / "out",
            provider_get=provider_get,
        )
    assert called is False


def test_probe_rejects_market_fields() -> None:
    payload = json.loads(_payload())
    payload["result"][0]["odds"] = {"home": "1.5"}
    with pytest.raises(ValueError, match="downstream market fields"):
        inspect_fixture_payload(
            json.dumps(payload).encode(),
            requested_date="2026-09-16",
        )


def test_probe_records_but_does_not_auto_admit_unknown_actual_start_field() -> None:
    payload = json.loads(_payload())
    payload["result"][0]["started_at"] = "2026-09-16T14:13:00Z"
    audit = inspect_fixture_payload(
        json.dumps(payload).encode(),
        requested_date="2026-09-16",
    )
    assert "$.result[0].started_at" in audit.separate_actual_start_field_paths
    assert audit.historical_actual_start_admissible is False
