from __future__ import annotations

from datetime import date

import pytest

from tennis_genome.experiments.pattern_confirm_sportradar_client import (
    fetch_competitor_profile,
    fetch_daily_summaries,
    fetch_daily_summary_range,
    fetch_season_info,
    fetch_sport_event_summary,
)


def _recorder(payloads: list[object]):
    calls: list[tuple[str, dict[str, str]]] = []

    def get_json(url: str, *, headers: dict[str, str]) -> object:
        calls.append((url, headers))
        return payloads[len(calls) - 1]

    return calls, get_json


def test_fixed_endpoints_use_header_key_not_query_string() -> None:
    calls, get_json = _recorder([{}, {}, {}])
    fetch_sport_event_summary(
        "sr:sport_event:1",
        api_key="secret",
        access_level="trial",
        get_json=get_json,
    )
    fetch_season_info(
        "sr:season:1",
        api_key="secret",
        access_level="trial",
        get_json=get_json,
    )
    fetch_competitor_profile(
        "sr:competitor:1",
        api_key="secret",
        access_level="trial",
        get_json=get_json,
    )
    assert calls[0][0].endswith("/sport_events/sr:sport_event:1/summary.json")
    assert calls[1][0].endswith("/seasons/sr:season:1/info.json")
    assert calls[2][0].endswith("/competitors/sr:competitor:1/profile.json")
    assert all("secret" not in url for url, _ in calls)
    assert all(headers == {"x-api-key": "secret"} for _, headers in calls)


def test_daily_range_is_end_exclusive_and_deterministic() -> None:
    calls, get_json = _recorder(
        [
            {"summaries": [{"sport_event": {"id": "a"}}]},
            {"summaries": [{"sport_event": {"id": "b"}}]},
        ]
    )
    rows = fetch_daily_summary_range(
        date(2026, 1, 1),
        date(2026, 1, 3),
        api_key="secret",
        access_level="production",
        get_json=get_json,
    )
    assert [row["sport_event"]["id"] for row in rows] == ["a", "b"]
    assert calls[0][0].endswith("/schedules/2026-01-01/summaries.json")
    assert calls[1][0].endswith("/schedules/2026-01-02/summaries.json")


def test_daily_parser_and_configuration_fail_closed() -> None:
    _, bad = _recorder([{"summaries": "wrong"}])
    with pytest.raises(ValueError, match="array"):
        fetch_daily_summaries(
            date(2026, 1, 1),
            api_key="secret",
            access_level="trial",
            get_json=bad,
        )
    with pytest.raises(ValueError, match="access level"):
        fetch_season_info(
            "sr:season:1",
            api_key="secret",
            access_level="invalid",
            get_json=lambda *args, **kwargs: {},
        )
    with pytest.raises(ValueError, match="non-empty"):
        fetch_season_info(
            "sr:season:1",
            api_key="",
            access_level="trial",
            get_json=lambda *args, **kwargs: {},
        )
    with pytest.raises(ValueError, match="after start"):
        fetch_daily_summary_range(
            date(2026, 1, 2),
            date(2026, 1, 2),
            api_key="secret",
            access_level="trial",
        )
