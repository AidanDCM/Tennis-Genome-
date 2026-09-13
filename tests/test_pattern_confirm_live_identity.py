from __future__ import annotations

from dataclasses import asdict

import pytest

from tennis_genome.experiments.pattern_confirm_live_identity import (
    build_identity_mapping,
    parse_sportradar_actual_start,
    parse_sportradar_prematch_event,
    resolve_exact_context_unique,
    validate_mapping_against_event,
    verify_identity_mapping,
)


def _summary(
    *,
    event_id: str = "sr:sport_event:123",
    start: str = "2026-09-12T17:00:00+00:00",
    confirmed: bool = True,
    status: str = "not_started",
    competition_type: str = "singles",
    category_id: str = "sr:category:3",
    category_name: str = "ATP",
    home_id: str = "sr:competitor:11",
    away_id: str = "sr:competitor:22",
    home_name: str = "Paul, Tommy",
    away_name: str = "Fritz, Taylor",
    competition_name: str = "ATP Miami, USA Men Singles",
) -> dict[str, object]:
    return {
        "sport_event": {
            "id": event_id,
            "start_time": start,
            "start_time_confirmed": confirmed,
            "sport_event_context": {
                "category": {"id": category_id, "name": category_name},
                "competition": {
                    "id": "sr:competition:55",
                    "name": competition_name,
                    "type": competition_type,
                },
                "season": {
                    "id": "sr:season:2026-test",
                    "name": "ATP Miami 2026",
                    "start_date": "2026-09-07",
                    "end_date": "2026-09-20",
                    "year": "2026",
                    "competition_id": "sr:competition:55",
                },
            },
            "competitors": [
                {
                    "id": home_id,
                    "name": home_name,
                    "qualifier": "home",
                    "virtual": False,
                },
                {
                    "id": away_id,
                    "name": away_name,
                    "qualifier": "away",
                    "virtual": False,
                },
            ],
        },
        "sport_event_status": {"status": status},
    }


def _mapping():
    event = parse_sportradar_prematch_event(_summary())
    return build_identity_mapping(
        market_event_id="odds-event-1",
        market_player_a_name="Paul, Tommy",
        market_player_b_name="Fritz, Taylor",
        player_a_canonical_id="tommy_paul",
        player_b_canonical_id="taylor_fritz",
        sportradar_event=event,
        method="EXPLICIT_CROSSWALK",
        created_at="2026-09-12T15:00:00+00:00",
    )


def test_prematch_event_requires_atp_singles_confirmed_and_not_started() -> None:
    event = parse_sportradar_prematch_event(_summary())
    assert event.sport_event_id == "sr:sport_event:123"
    assert event.player_a_sportradar_id == "sr:competitor:11"
    assert event.player_b_sportradar_id == "sr:competitor:22"
    assert event.competition_type == "singles"

    with pytest.raises(ValueError, match="start_time_confirmed"):
        parse_sportradar_prematch_event(_summary(confirmed=False))
    with pytest.raises(ValueError, match="not ATP"):
        parse_sportradar_prematch_event(_summary(category_id="sr:category:6", category_name="WTA"))
    with pytest.raises(ValueError, match="singles"):
        parse_sportradar_prematch_event(_summary(competition_type="doubles"))
    with pytest.raises(ValueError, match="pre-match"):
        parse_sportradar_prematch_event(_summary(status="live"))


def test_identity_mapping_is_deterministic_and_tamper_evident() -> None:
    first = _mapping()
    second = _mapping()
    assert first.artifact_sha256 == second.artifact_sha256
    assert verify_identity_mapping(asdict(first)) == first

    tampered = asdict(first)
    tampered["player_a_canonical_id"] = "somebody_else"
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_identity_mapping(tampered)


def test_identity_mapping_rejects_duplicate_players_and_post_start_creation() -> None:
    event = parse_sportradar_prematch_event(_summary())
    with pytest.raises(ValueError, match="canonical player IDs must differ"):
        build_identity_mapping(
            market_event_id="odds-event-1",
            market_player_a_name="Paul, Tommy",
            market_player_b_name="Fritz, Taylor",
            player_a_canonical_id="same",
            player_b_canonical_id="same",
            sportradar_event=event,
            method="EXPLICIT_CROSSWALK",
            created_at="2026-09-12T15:00:00+00:00",
        )
    with pytest.raises(ValueError, match="before scheduled start"):
        build_identity_mapping(
            market_event_id="odds-event-1",
            market_player_a_name="Paul, Tommy",
            market_player_b_name="Fritz, Taylor",
            player_a_canonical_id="tommy_paul",
            player_b_canonical_id="taylor_fritz",
            sportradar_event=event,
            method="MANUAL_PREMATCH",
            created_at="2026-09-12T17:00:00+00:00",
        )


def test_mapping_must_still_match_event_and_orientation() -> None:
    mapping = _mapping()
    validate_mapping_against_event(mapping, parse_sportradar_prematch_event(_summary()))

    swapped = parse_sportradar_prematch_event(
        _summary(
            home_id="sr:competitor:22",
            away_id="sr:competitor:11",
            home_name="Fritz, Taylor",
            away_name="Paul, Tommy",
        )
    )
    with pytest.raises(ValueError, match="player A"):
        validate_mapping_against_event(mapping, swapped)


def test_exact_context_resolver_requires_unique_exact_names_not_fuzzy() -> None:
    mapping = resolve_exact_context_unique(
        market_event_id="odds-event-1",
        market_player_a_name="Paul Tommy",
        market_player_b_name="Fritz Taylor",
        player_a_canonical_id="tommy_paul",
        player_b_canonical_id="taylor_fritz",
        market_scheduled_start="2026-09-12T17:05:00+00:00",
        market_competition_name="ATP Miami USA Men Singles",
        candidate_payloads=[_summary()],
        created_at="2026-09-12T15:00:00+00:00",
    )
    assert mapping.method == "EXACT_CONTEXT_UNIQUE"
    assert mapping.player_a_sportradar_id == "sr:competitor:11"

    with pytest.raises(ValueError, match="found 0"):
        resolve_exact_context_unique(
            market_event_id="odds-event-1",
            market_player_a_name="Tommy Pau",
            market_player_b_name="Taylor Fritz",
            player_a_canonical_id="tommy_paul",
            player_b_canonical_id="taylor_fritz",
            market_scheduled_start="2026-09-12T17:05:00+00:00",
            market_competition_name="ATP Miami USA Men Singles",
            candidate_payloads=[_summary()],
            created_at="2026-09-12T15:00:00+00:00",
        )

    with pytest.raises(ValueError, match="found 2"):
        resolve_exact_context_unique(
            market_event_id="odds-event-1",
            market_player_a_name="Paul Tommy",
            market_player_b_name="Fritz Taylor",
            player_a_canonical_id="tommy_paul",
            player_b_canonical_id="taylor_fritz",
            market_scheduled_start="2026-09-12T17:05:00+00:00",
            market_competition_name="ATP Miami USA Men Singles",
            candidate_payloads=[_summary(), _summary(event_id="sr:sport_event:456")],
            created_at="2026-09-12T15:00:00+00:00",
        )


def test_exact_context_resolver_orients_market_players_to_sportradar_home_away() -> None:
    mapping = resolve_exact_context_unique(
        market_event_id="odds-event-1",
        market_player_a_name="Fritz Taylor",
        market_player_b_name="Paul Tommy",
        player_a_canonical_id="taylor_fritz",
        player_b_canonical_id="tommy_paul",
        market_scheduled_start="2026-09-12T17:00:00+00:00",
        market_competition_name="ATP Miami USA Men Singles",
        candidate_payloads=[_summary()],
        created_at="2026-09-12T15:00:00+00:00",
    )
    assert mapping.player_a_sportradar_id == "sr:competitor:11"
    assert mapping.player_a_canonical_id == "tommy_paul"
    assert mapping.player_b_canonical_id == "taylor_fritz"


def test_timeline_uses_earliest_match_started_and_never_falls_back() -> None:
    payload = {
        "sport_event": {"id": "sr:sport_event:123"},
        "timeline": [
            {
                "id": 2,
                "type": "point",
                "time": "2026-09-12T17:03:00+00:00",
            },
            {
                "id": 3,
                "type": "match_started",
                "time": "2026-09-12T17:02:00+00:00",
            },
            {
                "id": 1,
                "type": "match_started",
                "time": "2026-09-12T17:01:30+00:00",
            },
        ],
    }
    result = parse_sportradar_actual_start(payload, expected_event_id="sr:sport_event:123")
    assert result.actual_start == "2026-09-12T17:01:30+00:00"
    assert result.exclusion_reason is None

    missing = parse_sportradar_actual_start(
        {
            "sport_event": {
                "id": "sr:sport_event:123",
                "start_time": "2026-09-12T17:00:00+00:00",
            },
            "timeline": [
                {
                    "id": 2,
                    "type": "point",
                    "time": "2026-09-12T17:03:00+00:00",
                }
            ],
        },
        expected_event_id="sr:sport_event:123",
    )
    assert missing.actual_start is None
    assert missing.exclusion_reason == "ACTUAL_START_UNVERIFIED"


def test_timeline_wrong_event_or_naive_timestamp_fails_closed() -> None:
    with pytest.raises(ValueError, match="event ID mismatch"):
        parse_sportradar_actual_start(
            {"sport_event": {"id": "wrong"}, "timeline": []},
            expected_event_id="sr:sport_event:123",
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        parse_sportradar_actual_start(
            {
                "sport_event": {"id": "sr:sport_event:123"},
                "timeline": [
                    {
                        "id": 1,
                        "type": "match_started",
                        "time": "2026-09-12T17:01:30",
                    }
                ],
            },
            expected_event_id="sr:sport_event:123",
        )


def test_prematch_event_requires_explicit_provider_status() -> None:
    payload = _summary()
    payload.pop("sport_event_status")
    with pytest.raises(ValueError, match="status must be non-empty"):
        parse_sportradar_prematch_event(payload)

    payload = _summary()
    payload["sport_event_status"] = {}
    with pytest.raises(ValueError, match="status must be non-empty"):
        parse_sportradar_prematch_event(payload)
