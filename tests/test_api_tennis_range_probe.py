from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from tennis_genome.research_workbench.api_tennis_range_probe import (
    capture_api_tennis_range_probe,
    inspect_range_payload,
)


def _fixture(*, event_key: int, event_date: str, tour: str = "Atp Singles") -> dict[str, object]:
    return {
        "event_key": event_key,
        "event_date": event_date,
        "event_time": "12:00",
        "event_type_type": tour,
        "event_status": "Finished",
        "scores": [{"score_first": "6", "score_second": "4"}],
        "pointbypoint": [{"set_number": 1, "number_game": 1}],
        "statistics": [{"stat_name": "Aces", "stat_value": "4"}],
    }


def _raw(*fixtures: dict[str, object]) -> bytes:
    return json.dumps({"success": 1, "result": list(fixtures)}).encode("utf-8")


def test_range_probe_counts_one_week_payload() -> None:
    raw = _raw(
        _fixture(event_key=1, event_date="2026-09-10"),
        _fixture(event_key=2, event_date="2026-09-12", tour="Wta Singles"),
        _fixture(event_key=3, event_date="2026-09-16", tour="Challenger Men Singles"),
    )

    audit = inspect_range_payload(
        raw,
        date_start="2026-09-10",
        date_stop="2026-09-16",
    )

    assert audit.span_days == 7
    assert audit.provider_request_count == 1
    assert audit.fixture_count == 3
    assert audit.atp_singles_count == 1
    assert audit.wta_singles_count == 1
    assert audit.finished_count == 3
    assert audit.pointbypoint_nonempty_count == 3
    assert audit.statistics_nonempty_count == 3
    assert audit.scores_nonempty_count == 3
    assert audit.event_dates == ("2026-09-10", "2026-09-12", "2026-09-16")
    assert audit.historical_actual_start_admissible is False


def test_range_probe_rejects_fixture_outside_requested_range() -> None:
    raw = _raw(_fixture(event_key=1, event_date="2026-09-17"))

    with pytest.raises(ValueError, match="outside requested date range"):
        inspect_range_payload(
            raw,
            date_start="2026-09-10",
            date_stop="2026-09-16",
        )


def test_range_probe_rejects_ranges_above_seven_days() -> None:
    with pytest.raises(ValueError, match="between one and seven"):
        inspect_range_payload(
            _raw(),
            date_start="2026-09-01",
            date_stop="2026-09-08",
        )


def test_range_probe_rejects_unexpected_market_fields() -> None:
    fixture = _fixture(event_key=1, event_date="2026-09-10")
    fixture["bookmaker"] = "unexpected"

    with pytest.raises(ValueError, match="downstream market fields"):
        inspect_range_payload(
            _raw(fixture),
            date_start="2026-09-10",
            date_stop="2026-09-16",
        )


def test_capture_spends_one_request_and_does_not_persist_key(tmp_path: Path) -> None:
    calls: list[str] = []
    raw = _raw(
        _fixture(event_key=1, event_date="2026-09-10"),
        _fixture(event_key=2, event_date="2026-09-16", tour="Wta Singles"),
    )

    def provider_get(url: str) -> bytes:
        calls.append(url)
        return raw

    api_key = "super-secret-api-key"
    audit = capture_api_tennis_range_probe(
        date_start="2026-09-10",
        date_stop="2026-09-16",
        api_key=api_key,
        output_dir=tmp_path,
        provider_get=provider_get,
    )

    assert audit.provider_request_count == 1
    assert len(calls) == 1
    query = parse_qs(urlparse(calls[0]).query)
    assert query["method"] == ["get_fixtures"]
    assert query["date_start"] == ["2026-09-10"]
    assert query["date_stop"] == ["2026-09-16"]
    assert query["timezone"] == ["UTC"]
    assert query["APIkey"] == [api_key]

    retained = b"\n".join(path.read_bytes() for path in sorted(tmp_path.iterdir()))
    assert api_key.encode("utf-8") not in retained
