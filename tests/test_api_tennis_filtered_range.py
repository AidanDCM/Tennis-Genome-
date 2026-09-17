from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from tennis_genome.research_workbench.api_tennis_filtered_range import (
    capture_api_tennis_filtered_range,
    serve_return_fixture_input_sha256,
)


def _fixture(
    *,
    event_key: int,
    event_date: str,
    event_type_key: str,
    event_type_type: str,
    score: str = "6-4",
) -> dict[str, object]:
    return {
        "event_key": event_key,
        "event_date": event_date,
        "event_time": "12:00",
        "event_type_key": event_type_key,
        "event_type_type": event_type_type,
        "event_status": "Finished",
        "event_winner": "First Player",
        "first_player_key": 1000 + event_key,
        "second_player_key": 2000 + event_key,
        "scores": [{"score": score}],
        "pointbypoint": [{"set_number": 1, "number_game": 1}],
        "statistics": [
            {
                "player_key": 1000 + event_key,
                "stat_period": "match",
                "stat_name": "Service Points Won",
                "stat_won": 20,
                "stat_total": 40,
            }
        ],
    }


def _raw(*rows: dict[str, object]) -> bytes:
    return json.dumps({"success": 1, "result": list(rows)}).encode("utf-8")


def test_filtered_capture_spends_exactly_two_requests_and_filters(tmp_path: Path) -> None:
    calls: list[str] = []

    def provider_get(url: str) -> bytes:
        calls.append(url)
        query = parse_qs(urlparse(url).query)
        event_type_key = query["event_type_key"][0]
        if event_type_key == "265":
            return _raw(
                _fixture(
                    event_key=1,
                    event_date="2026-09-10",
                    event_type_key="265",
                    event_type_type="Atp Singles",
                )
            )
        if event_type_key == "266":
            return _raw(
                _fixture(
                    event_key=2,
                    event_date="2026-09-16",
                    event_type_key="266",
                    event_type_type="Wta Singles",
                )
            )
        raise AssertionError("unexpected event_type_key")

    api_key = "secret"
    audit = capture_api_tennis_filtered_range(
        date_start="2026-09-10",
        date_stop="2026-09-16",
        api_key=api_key,
        output_dir=tmp_path,
        provider_get=provider_get,
    )

    assert len(calls) == 2
    assert audit.provider_request_count == 2
    assert audit.atp_fixture_count == 1
    assert audit.wta_fixture_count == 1
    assert audit.event_key_count == 2
    assert audit.statistics_nonempty_count == 2
    assert audit.pointbypoint_nonempty_count == 2
    for url in calls:
        query = parse_qs(urlparse(url).query)
        assert query["method"] == ["get_fixtures"]
        assert query["date_start"] == ["2026-09-10"]
        assert query["date_stop"] == ["2026-09-16"]
        assert query["timezone"] == ["UTC"]
        assert query["APIkey"] == [api_key]
        assert query["event_type_key"][0] in {"265", "266"}

    retained = b"\n".join(path.read_bytes() for path in sorted(tmp_path.iterdir()))
    assert api_key.encode() not in retained


def test_serve_return_hash_ignores_score_and_clock_formatting() -> None:
    base = _fixture(
        event_key=1,
        event_date="2026-09-10",
        event_type_key="265",
        event_type_type="Atp Singles",
    )
    revised = dict(base)
    revised["event_time"] = "12:05"
    revised["scores"] = [{"score": "6-4 (7-5)"}]
    revised["pointbypoint"] = [{"provider_format_revision": True}]

    assert serve_return_fixture_input_sha256(base) == serve_return_fixture_input_sha256(
        revised
    )


def test_serve_return_hash_changes_when_statistics_change() -> None:
    base = _fixture(
        event_key=1,
        event_date="2026-09-10",
        event_type_key="265",
        event_type_type="Atp Singles",
    )
    revised = json.loads(json.dumps(base))
    revised["statistics"][0]["stat_won"] = 21

    assert serve_return_fixture_input_sha256(base) != serve_return_fixture_input_sha256(
        revised
    )


def test_filtered_capture_rejects_wrong_tour_response(tmp_path: Path) -> None:
    def provider_get(url: str) -> bytes:
        query = parse_qs(urlparse(url).query)
        event_type_key = query["event_type_key"][0]
        return _raw(
            _fixture(
                event_key=1,
                event_date="2026-09-10",
                event_type_key=event_type_key,
                event_type_type="Wta Singles",
            )
        )

    with pytest.raises(ValueError, match="wrong event type"):
        capture_api_tennis_filtered_range(
            date_start="2026-09-10",
            date_stop="2026-09-16",
            api_key="secret",
            output_dir=tmp_path,
            provider_get=provider_get,
        )


def test_filtered_capture_rejects_duplicate_event_ids_across_tours(tmp_path: Path) -> None:
    def provider_get(url: str) -> bytes:
        query = parse_qs(urlparse(url).query)
        event_type_key = query["event_type_key"][0]
        event_type_type = "Atp Singles" if event_type_key == "265" else "Wta Singles"
        return _raw(
            _fixture(
                event_key=1,
                event_date="2026-09-10",
                event_type_key=event_type_key,
                event_type_type=event_type_type,
            )
        )

    with pytest.raises(ValueError, match="duplicate event_key"):
        capture_api_tennis_filtered_range(
            date_start="2026-09-10",
            date_stop="2026-09-16",
            api_key="secret",
            output_dir=tmp_path,
            provider_get=provider_get,
        )


def test_filtered_capture_rejects_ranges_above_31_days(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="between one and 31"):
        capture_api_tennis_filtered_range(
            date_start="2026-08-01",
            date_stop="2026-09-16",
            api_key="secret",
            output_dir=tmp_path,
        )
