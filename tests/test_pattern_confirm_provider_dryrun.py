from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tennis_genome.experiments.pattern_confirm_provider_dryrun import (
    build_snapshot,
    capture_live_snapshot,
    compare_snapshots,
    discover_tennis_sport_keys,
    parse_pinnacle_candidates,
    parse_sportradar_candidates,
    snapshot_as_dict,
    verify_snapshot,
)


def _sports() -> list[dict[str, object]]:
    return [
        {
            "key": "tennis_atp_test",
            "group": "Tennis",
            "title": "ATP Test",
            "active": True,
            "has_outrights": False,
        },
        {
            "key": "tennis_wta_test",
            "group": "Tennis",
            "title": "WTA Test",
            "active": True,
            "has_outrights": False,
        },
        {
            "key": "americanfootball_nfl",
            "group": "American Football",
            "title": "NFL",
            "active": True,
            "has_outrights": False,
        },
        {
            "key": "tennis_inactive",
            "group": "Tennis",
            "title": "Old",
            "active": False,
            "has_outrights": False,
        },
    ]


def _odds_event(
    index: int,
    *,
    start: datetime,
    last_update: datetime,
    sport_key: str = "tennis_atp_test",
) -> dict[str, object]:
    player_a = f"Player A{index}"
    player_b = f"Player B{index}"
    return {
        "id": f"odds-{index}",
        "sport_key": sport_key,
        "sport_title": "ATP Miami Open",
        "commence_time": start.isoformat().replace("+00:00", "Z"),
        "home_team": player_a,
        "away_team": player_b,
        "bookmakers": [
            {
                "key": "pinnacle",
                "title": "Pinnacle",
                "last_update": last_update.isoformat().replace("+00:00", "Z"),
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": player_a, "price": 1.8},
                            {"name": player_b, "price": 2.1},
                        ],
                    }
                ],
            }
        ],
    }


def _sportradar_summary(index: int, *, start: datetime) -> dict[str, object]:
    return {
        "sport_event": {
            "id": f"sr:sport_event:{1000 + index}",
            "start_time": start.isoformat(),
            "start_time_confirmed": True,
            "sport_event_context": {
                "sport": {"id": "sr:sport:5", "name": "Tennis"},
                "category": {"id": "sr:category:3", "name": "ATP"},
                "competition": {
                    "id": "sr:competition:55",
                    "name": "ATP Miami Open Men Singles",
                    "type": "singles",
                    "gender": "men",
                },
            },
            "competitors": [
                {
                    "id": f"sr:competitor:{2000 + index * 2}",
                    "name": f"Player A{index}",
                    "qualifier": "home",
                    "virtual": False,
                },
                {
                    "id": f"sr:competitor:{2001 + index * 2}",
                    "name": f"Player B{index}",
                    "qualifier": "away",
                    "virtual": False,
                },
            ],
        },
        "sport_event_status": {"status": "not_started"},
    }


def _snapshot(captured: datetime, *, count: int = 3):
    start = captured + timedelta(hours=4)
    odds = [
        _odds_event(i, start=start + timedelta(minutes=20 * i), last_update=captured)
        for i in range(count)
    ]
    summaries = [
        _sportradar_summary(i, start=start + timedelta(minutes=20 * i)) for i in range(count)
    ]
    return build_snapshot(
        captured_at=captured.isoformat(),
        queried_utc_dates=((captured.date() + timedelta(days=1)).isoformat(),),
        sports_payload=[_sports()[0]],
        odds_payloads={"tennis_atp_test": odds},
        sportradar_payloads={
            (captured.date() + timedelta(days=1)).isoformat(): {"summaries": summaries}
        },
    )


def test_discovers_only_active_tennis_sports() -> None:
    assert discover_tennis_sport_keys(_sports()) == ("tennis_atp_test", "tennis_wta_test")


def test_pinnacle_parser_is_two_sided_and_reproduces_devig() -> None:
    captured = datetime(2026, 9, 12, 12, tzinfo=UTC)
    event = _odds_event(0, start=captured + timedelta(hours=2), last_update=captured)
    candidates, raw_count = parse_pinnacle_candidates(
        [event], sport_key="tennis_atp_test", captured_at=captured.isoformat()
    )
    assert raw_count == 1
    assert len(candidates) == 1
    candidate = candidates[0]
    expected = (1 / 1.8) / ((1 / 1.8) + (1 / 2.1))
    assert candidate.market_probability_a == pytest.approx(expected)
    assert candidate.quote_fresh is True


def test_pinnacle_parser_rejects_outcome_identity_mismatch() -> None:
    captured = datetime(2026, 9, 12, 12, tzinfo=UTC)
    event = _odds_event(0, start=captured + timedelta(hours=2), last_update=captured)
    event["bookmakers"][0]["markets"][0]["outcomes"][1]["name"] = "Wrong Player"  # type: ignore[index]
    with pytest.raises(ValueError, match="do not match event competitors"):
        parse_pinnacle_candidates(
            [event], sport_key="tennis_atp_test", captured_at=captured.isoformat()
        )


def test_sportradar_parser_reuses_frozen_prematch_contract() -> None:
    start = datetime(2026, 9, 13, 15, tzinfo=UTC)
    events, raw_count = parse_sportradar_candidates(
        {"summaries": [_sportradar_summary(0, start=start)]}
    )
    assert raw_count == 1
    assert len(events) == 1
    assert events[0].sport_event_id == "sr:sport_event:1000"

    invalid = _sportradar_summary(1, start=start)
    invalid["sport_event_status"] = {"status": "live"}
    events, raw_count = parse_sportradar_candidates({"summaries": [invalid]})
    assert raw_count == 1
    assert events == []


def test_snapshot_is_self_hashed_and_contains_no_secret_fields() -> None:
    captured = datetime(2026, 9, 12, 12, tzinfo=UTC)
    snapshot = _snapshot(captured, count=1)
    verified = verify_snapshot(snapshot_as_dict(snapshot))
    assert verified.artifact_sha256 == snapshot.artifact_sha256
    serialized = str(snapshot_as_dict(snapshot)).lower()
    assert "api_key" not in serialized
    assert "secret" not in serialized


def test_three_stable_events_across_five_minutes_pass_transport_gate() -> None:
    first_time = datetime(2026, 9, 12, 12, tzinfo=UTC)
    second_time = first_time + timedelta(minutes=5)
    first = _snapshot(first_time, count=3)
    second = _snapshot(second_time, count=3)
    report = compare_snapshots(first, second)
    assert report.status == "TRANSPORT_COMPATIBLE"
    assert report.stable_event_count == 3
    assert report.outcome_blind is True


def test_less_than_three_events_is_insufficient_sample_not_failure() -> None:
    first_time = datetime(2026, 9, 12, 12, tzinfo=UTC)
    first = _snapshot(first_time, count=2)
    second = _snapshot(first_time + timedelta(minutes=5), count=2)
    report = compare_snapshots(first, second)
    assert report.status == "INSUFFICIENT_LIVE_SAMPLE"
    assert "FEWER_THAN_THREE_PINNACLE_EVENTS" in report.reasons


def test_snapshots_under_five_minutes_fail_closed() -> None:
    first_time = datetime(2026, 9, 12, 12, tzinfo=UTC)
    first = _snapshot(first_time, count=3)
    second = _snapshot(first_time + timedelta(minutes=4, seconds=59), count=3)
    report = compare_snapshots(first, second)
    assert report.status == "FAIL_CLOSED"
    assert "SNAPSHOTS_LESS_THAN_FIVE_MINUTES_APART" in report.reasons


def test_stale_quotes_cannot_satisfy_transport_compatibility() -> None:
    first_time = datetime(2026, 9, 12, 12, tzinfo=UTC)
    start = first_time + timedelta(hours=4)
    odds = [
        _odds_event(
            i,
            start=start + timedelta(minutes=20 * i),
            last_update=first_time - timedelta(minutes=6),
        )
        for i in range(3)
    ]
    summaries = [_sportradar_summary(i, start=start + timedelta(minutes=20 * i)) for i in range(3)]
    first = build_snapshot(
        captured_at=first_time.isoformat(),
        queried_utc_dates=("2026-09-13",),
        sports_payload=[_sports()[0]],
        odds_payloads={"tennis_atp_test": odds},
        sportradar_payloads={"2026-09-13": {"summaries": summaries}},
    )
    second_time = first_time + timedelta(minutes=5)
    odds_second = [
        _odds_event(
            i,
            start=start + timedelta(minutes=20 * i),
            last_update=second_time - timedelta(minutes=6),
        )
        for i in range(3)
    ]
    second = build_snapshot(
        captured_at=second_time.isoformat(),
        queried_utc_dates=("2026-09-13",),
        sports_payload=[_sports()[0]],
        odds_payloads={"tennis_atp_test": odds_second},
        sportradar_payloads={"2026-09-13": {"summaries": summaries}},
    )
    report = compare_snapshots(first, second)
    assert report.status == "FAIL_CLOSED"
    assert "FEWER_THAN_THREE_STABLE_FRESH_ALIGNED_EVENTS" in report.reasons


def test_live_capture_never_serializes_keys_and_queries_future_dates() -> None:
    now = datetime(2026, 9, 12, 23, 30, tzinfo=UTC)
    seen: list[tuple[str, dict[str, str] | None]] = []

    def fake_get(url: str, *, headers: dict[str, str] | None = None) -> object:
        seen.append((url, headers))
        if "/v4/sports/?" in url:
            return [_sports()[0]]
        if "/odds/?" in url:
            return []
        if "/schedules/2026-09-13/summaries.json" in url:
            return {"summaries": []}
        if "/schedules/2026-09-14/summaries.json" in url:
            return {"summaries": []}
        raise AssertionError(url)

    snapshot = capture_live_snapshot(
        odds_api_key="odds-secret",
        sportradar_api_key="sr-secret",
        sportradar_access_level="trial",
        now=now,
        get_json=fake_get,
    )
    assert snapshot.queried_utc_dates == ("2026-09-13", "2026-09-14")
    serialized = str(snapshot_as_dict(snapshot))
    assert "odds-secret" not in serialized
    assert "sr-secret" not in serialized
    assert any("apiKey=odds-secret" in url for url, _ in seen)
    assert any(headers == {"x-api-key": "sr-secret"} for _, headers in seen)
