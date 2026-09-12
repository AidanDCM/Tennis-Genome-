from __future__ import annotations

import pytest

from tennis_genome.experiments.pattern_confirm_live_identity import (
    build_identity_mapping,
    parse_sportradar_prematch_event,
)
from tennis_genome.experiments.pattern_confirm_sportradar_state import (
    build_state_bundle,
    build_target_context_artifact,
    history_from_state_bundle,
    map_handedness,
    map_level,
    map_round,
    map_surface,
    state_bundle_as_dict,
    target_context_as_dict,
    target_pre_match,
    verify_state_bundle,
    verify_target_context_artifact,
)


def _summary(
    *,
    event_id: str = "sr:sport_event:1",
    status: str = "not_started",
    winner_id: str | None = None,
    winning_reason: str | None = None,
    round_name: str = "quarterfinal",
    level: str = "atp_1000",
    home_id: str = "sr:competitor:11",
    away_id: str = "sr:competitor:22",
    season_id: str = "sr:season:2026-test",
    season_start: str = "2026-09-07",
    include_stats: bool = True,
) -> dict[str, object]:
    status_payload: dict[str, object] = {"status": status}
    if winner_id is not None:
        status_payload["winner_id"] = winner_id
    if winning_reason is not None:
        status_payload["winning_reason"] = winning_reason
    payload: dict[str, object] = {
        "sport_event": {
            "id": event_id,
            "start_time": "2026-09-12T17:00:00+00:00",
            "start_time_confirmed": True,
            "sport_event_context": {
                "category": {"id": "sr:category:3", "name": "ATP"},
                "competition": {
                    "id": "sr:competition:55",
                    "name": "ATP Test Men Singles",
                    "type": "singles",
                    "level": level,
                },
                "season": {
                    "id": season_id,
                    "name": "ATP Test 2026",
                    "start_date": season_start,
                    "end_date": "2026-09-20",
                    "year": "2026",
                    "competition_id": "sr:competition:55",
                },
                "round": {"name": round_name},
                "mode": {"best_of": 3},
            },
            "competitors": [
                {
                    "id": home_id,
                    "name": "Paul, Tommy",
                    "qualifier": "home",
                    "country_code": "USA",
                    "seed": 4,
                    "virtual": False,
                },
                {
                    "id": away_id,
                    "name": "Fritz, Taylor",
                    "qualifier": "away",
                    "country_code": "USA",
                    "seed": 2,
                    "virtual": False,
                },
            ],
        },
        "sport_event_status": status_payload,
    }
    if include_stats:
        payload["statistics"] = {
            "totals": {
                "competitors": [
                    {
                        "id": home_id,
                        "qualifier": "home",
                        "statistics": {
                            "aces": 6,
                            "double_faults": 2,
                            "first_serve_points_won": 32,
                            "second_serve_points_won": 18,
                            "first_serve_successful": 45,
                            "service_points_won": 50,
                            "service_points_lost": 30,
                        },
                    },
                    {
                        "id": away_id,
                        "qualifier": "away",
                        "statistics": {
                            "aces": 8,
                            "double_faults": 1,
                            "first_serve_points_won": 30,
                            "second_serve_points_won": 15,
                            "first_serve_successful": 43,
                            "service_points_won": 45,
                            "service_points_lost": 35,
                        },
                    },
                ]
            }
        }
    return payload


def _mapping():
    event = parse_sportradar_prematch_event(_summary(include_stats=False))
    return build_identity_mapping(
        market_event_id="odds-1",
        market_player_a_name="Tommy Paul",
        market_player_b_name="Taylor Fritz",
        player_a_canonical_id="canonical-a",
        player_b_canonical_id="canonical-b",
        sportradar_event=event,
        method="EXPLICIT_CROSSWALK",
        created_at="2026-09-12T15:00:00+00:00",
    )


def _season_info(surface: str = "hardcourt outdoor") -> dict[str, object]:
    return {
        "season": {
            "id": "sr:season:2026-test",
            "competition_id": "sr:competition:55",
            "competition": {
                "id": "sr:competition:55",
                "name": "ATP Test Men Singles",
                "type": "singles",
                "level": "atp_1000",
            },
            "info": {"surface": surface, "number_of_competitors": 64},
        }
    }


def _profile(competitor_id: str, *, dob: str, hand: str, height: int) -> dict[str, object]:
    return {
        "competitor": {
            "id": competitor_id,
            "name": "Player",
            "country_code": "USA",
        },
        "info": {
            "date_of_birth": dob,
            "handedness": hand,
            "height": height,
        },
    }


def test_frozen_enum_maps_are_fail_closed() -> None:
    assert map_surface("hardcourt outdoor") == "Hard"
    assert map_surface("red-clay") == "Clay"
    assert map_surface(None) == "Unknown"
    assert map_level("grand_slam") == "G"
    assert map_level("atp_1000") == "M"
    assert map_round("quarterfinal") == "QF"
    assert map_round("qualification_round_2") == "Q2"
    assert map_handedness("right") == "R"
    with pytest.raises(ValueError, match="surface"):
        map_surface("synthetic_indoor")
    with pytest.raises(ValueError, match="level"):
        map_level("challenger")
    with pytest.raises(ValueError, match="round"):
        map_round("mystery_round")
    with pytest.raises(ValueError, match="handedness"):
        map_handedness("ambidextrous")


def test_target_context_is_deterministic_and_bound_to_identity() -> None:
    mapping = _mapping()
    artifact = build_target_context_artifact(
        match_id="future-1",
        identity_mapping=mapping,
        summary_payload=_summary(include_stats=False),
        season_info_payload=_season_info(),
        profile_a_payload=_profile("sr:competitor:11", dob="1997-05-17", hand="right", height=185),
        profile_b_payload=_profile("sr:competitor:22", dob="1997-10-28", hand="left", height=196),
    )
    verified = verify_target_context_artifact(
        target_context_as_dict(artifact), identity_mapping=mapping
    )
    state = target_pre_match(verified)
    assert state.event_date.isoformat() == "2026-09-07"
    assert state.tournament_id == mapping.season_id
    assert state.tournament_level == "M"
    assert state.surface == "Hard"
    assert state.round == "QF"
    assert state.best_of == 3
    assert state.seed_a == 4 and state.seed_b == 2
    assert state.entry_a is None and state.entry_b is None
    assert state.rank_a is None and state.rank_b is None
    assert state.hand_a == "R" and state.hand_b == "L"
    assert state.height_cm_a == 185 and state.height_cm_b == 196
    assert state.age_years_a is not None and state.age_years_a > 29


def test_target_context_rejects_wrong_profile_and_unknown_surface() -> None:
    mapping = _mapping()
    with pytest.raises(ValueError, match="profile ID"):
        build_target_context_artifact(
            match_id="future-1",
            identity_mapping=mapping,
            summary_payload=_summary(include_stats=False),
            season_info_payload=_season_info(),
            profile_a_payload=_profile("wrong", dob="1997-05-17", hand="right", height=185),
            profile_b_payload=_profile(
                "sr:competitor:22", dob="1997-10-28", hand="left", height=196
            ),
        )
    with pytest.raises(ValueError, match="surface"):
        build_target_context_artifact(
            match_id="future-1",
            identity_mapping=mapping,
            summary_payload=_summary(include_stats=False),
            season_info_payload=_season_info("synthetic_indoor"),
            profile_a_payload=_profile(
                "sr:competitor:11", dob="1997-05-17", hand="right", height=185
            ),
            profile_b_payload=_profile(
                "sr:competitor:22", dob="1997-10-28", hand="left", height=196
            ),
        )


def test_target_context_tamper_fails_self_hash() -> None:
    mapping = _mapping()
    artifact = build_target_context_artifact(
        match_id="future-1",
        identity_mapping=mapping,
        summary_payload=_summary(include_stats=False),
        season_info_payload=_season_info(),
        profile_a_payload=_profile("sr:competitor:11", dob="1997-05-17", hand="right", height=185),
        profile_b_payload=_profile("sr:competitor:22", dob="1997-10-28", hand="left", height=196),
    )
    payload = target_context_as_dict(artifact)
    payload["season_start_date"] = "2026-09-08"
    with pytest.raises(ValueError, match="digest"):
        verify_target_context_artifact(payload, identity_mapping=mapping)


def test_state_bundle_parses_outcome_and_service_points() -> None:
    crosswalk = {
        "sr:competitor:11": "canonical-a",
        "sr:competitor:22": "canonical-b",
    }
    completed = _summary(
        status="closed",
        winner_id="sr:competitor:11",
    )
    bundle = build_state_bundle(summaries=[completed], crosswalk=crosswalk)
    assert bundle.accepted_count == 1
    assert bundle.excluded_count == 0
    verified = verify_state_bundle(state_bundle_as_dict(bundle), crosswalk=crosswalk)
    history = history_from_state_bundle(verified)
    assert len(history) == 1
    match = history[0]
    assert match.pre_match.event_date.isoformat() == "2026-09-07"
    assert match.outcome.a_won is True
    assert match.outcome.retirement is False
    assert match.stats is not None
    assert match.stats.service_points_a == 80
    assert match.stats.service_points_b == 80
    assert match.stats.duration_minutes is None


def test_state_bundle_keeps_nonstandard_finishes_as_excluded_history_rows() -> None:
    crosswalk = {
        "sr:competitor:11": "canonical-a",
        "sr:competitor:22": "canonical-b",
    }
    retired = _summary(
        event_id="sr:sport_event:ret",
        status="ended",
        winner_id="sr:competitor:11",
        winning_reason="retirement",
    )
    walkover = _summary(
        event_id="sr:sport_event:wo",
        status="ended",
        winner_id="sr:competitor:22",
        winning_reason="walkover",
    )
    bundle = build_state_bundle(summaries=[retired, walkover], crosswalk=crosswalk)
    history = history_from_state_bundle(bundle)
    assert len(history) == 2
    assert {match.outcome.retirement for match in history} == {False, True}
    assert {match.outcome.walkover for match in history} == {False, True}
    assert all(match.stats is None for match in history)


def test_state_bundle_reports_unresolved_identity_and_bad_statistics() -> None:
    crosswalk = {"sr:competitor:11": "canonical-a"}
    unresolved = _summary(
        event_id="sr:sport_event:unresolved",
        status="closed",
        winner_id="sr:competitor:11",
    )
    bundle = build_state_bundle(summaries=[unresolved], crosswalk=crosswalk)
    assert bundle.accepted_count == 0
    assert bundle.excluded_count == 1
    assert "UNRESOLVED_CANONICAL_ID" in bundle.exclusions[0].reason

    crosswalk["sr:competitor:22"] = "canonical-b"
    inconsistent = _summary(
        event_id="sr:sport_event:bad-stats",
        status="closed",
        winner_id="sr:competitor:11",
    )
    stats = inconsistent["statistics"]["totals"]["competitors"][0]["statistics"]
    stats["service_points_won"] = 99
    bad_bundle = build_state_bundle(summaries=[inconsistent], crosswalk=crosswalk)
    assert bad_bundle.accepted_count == 0
    assert bad_bundle.excluded_count == 1
    assert "inconsistent" in bad_bundle.exclusions[0].reason


def test_state_bundle_is_order_invariant_and_crosswalk_bound() -> None:
    crosswalk = {
        "sr:competitor:11": "canonical-a",
        "sr:competitor:22": "canonical-b",
    }
    first = _summary(
        event_id="sr:sport_event:a",
        status="closed",
        winner_id="sr:competitor:11",
        season_start="2026-01-01",
    )
    second = _summary(
        event_id="sr:sport_event:b",
        status="closed",
        winner_id="sr:competitor:22",
        season_start="2026-02-01",
    )
    a = build_state_bundle(summaries=[first, second], crosswalk=crosswalk)
    b = build_state_bundle(summaries=[second, first], crosswalk=crosswalk)
    assert a.source_payload_sha256 == b.source_payload_sha256
    assert a.parsed_rows_sha256 == b.parsed_rows_sha256
    assert a.artifact_sha256 == b.artifact_sha256
    with pytest.raises(ValueError, match="crosswalk"):
        verify_state_bundle(
            state_bundle_as_dict(a),
            crosswalk={**crosswalk, "sr:competitor:33": "canonical-c"},
        )


def test_state_bundle_self_hash_detects_rehashed_row_change() -> None:
    crosswalk = {
        "sr:competitor:11": "canonical-a",
        "sr:competitor:22": "canonical-b",
    }
    bundle = build_state_bundle(
        summaries=[_summary(status="closed", winner_id="sr:competitor:11")],
        crosswalk=crosswalk,
    )
    payload = state_bundle_as_dict(bundle)
    payload["accepted_count"] = 2
    with pytest.raises(ValueError, match="digest"):
        verify_state_bundle(payload, crosswalk=crosswalk)


def test_state_bundle_rejects_statistics_orientation_mismatch() -> None:
    crosswalk = {
        "sr:competitor:11": "canonical-a",
        "sr:competitor:22": "canonical-b",
    }
    payload = _summary(
        event_id="sr:sport_event:stats-swap",
        status="closed",
        winner_id="sr:competitor:11",
    )
    totals = payload["statistics"]["totals"]["competitors"]
    totals[0]["id"], totals[1]["id"] = totals[1]["id"], totals[0]["id"]
    bundle = build_state_bundle(summaries=[payload], crosswalk=crosswalk)
    assert bundle.accepted_count == 0
    assert bundle.excluded_count == 1
    assert "statistics home competitor ID mismatch" in bundle.exclusions[0].reason
