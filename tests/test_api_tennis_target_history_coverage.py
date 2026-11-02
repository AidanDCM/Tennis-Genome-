from copy import deepcopy

import pytest

from scripts.audit_api_tennis_target_history_coverage import assess


def _inputs():
    identity = {
        "schema_version": "tennis-genome-api-tennis-history-identity-audit-v1",
        "captures": [
            {
                "date_stop": "2026-11-01",
                "retained_bytes_verified": True,
                "workflow_run_id": 11,
            }
        ],
        "production_admitted": False,
        "players": [
            {"tour": "WTA", "api_player_key": 1, "status": "EXACT_NAME_BIRTHDATE"},
            {"tour": "WTA", "api_player_key": 2, "status": "EXACT_NAME_BIRTHDATE"},
        ],
        "events": [
            {
                "tour": "WTA",
                "event_key": 100,
                "api_player_keys": [1, 2],
                "point_disposition": "POINT_CONSISTENT",
                "identity_tier": "BOTH_EXACT",
                "tournament_key": 5,
            },
            {
                "tour": "WTA",
                "event_key": 101,
                "api_player_keys": [1, 3],
                "point_disposition": "POINT_CONFLICT",
                "identity_tier": "NAME_ONLY_OR_MIXED",
                "tournament_key": 5,
            },
        ],
    }
    crosswalk = {
        "schema_version": "tennis-genome-api-tennis-crosswalk-proposals-v1",
        "schedule_date": "2026-11-03",
        "production_admitted": False,
        "matches": [
            {
                "event_key": 200,
                "tour": "WTA",
                "tournament_key": 5,
                "api_player_keys": [1, 2],
                "status": "EXACT_CANDIDATE",
            }
        ],
    }
    return identity, crosswalk


def test_counts_only_exact_consistent_history_for_pilot_shortlist() -> None:
    identity, crosswalk = _inputs()
    report = assess(identity, crosswalk)
    assert report["exact_target_count"] == 1
    assert report["matches"][0]["minimum_exact_consistent_history"] == 1
    assert report["matches"][0]["players"][0]["point_conflict"] == 1
    assert report["formal_prediction_count"] == 0
    assert report["matches"][0]["production_eligible"] is False


def test_rejects_history_reaching_target_and_crosswalk_conflict() -> None:
    identity, crosswalk = _inputs()
    late = deepcopy(identity)
    late["captures"][0]["date_stop"] = "2026-11-03"
    with pytest.raises(ValueError, match="reaches target date"):
        assess(late, crosswalk)

    conflicting = deepcopy(identity)
    conflicting["players"][0]["status"] = "NAME_ONLY_PROPOSAL"
    with pytest.raises(ValueError, match="conflicts"):
        assess(conflicting, crosswalk)
