from __future__ import annotations

import json

import pytest

from tennis_genome.prospective import pilot


def _settlement_payload(reason: str) -> bytes:
    return (
        json.dumps(
            {
                "schema_version": "full-stack-pilot-sportradar-settlement-v1",
                "match_id": "pilot-match-terminal",
                "sportradar_event_id": "sr:sport_event:terminal",
                "player_a_canonical_id": "canonical-a",
                "player_b_canonical_id": "canonical-b",
                "player_a_sportradar_id": "sr:competitor:a",
                "player_b_sportradar_id": "sr:competitor:b",
                "observed_at": "2026-09-14T18:00:00+00:00",
                "sportradar_timeline": {
                    "sport_event": {"id": "sr:sport_event:terminal"},
                    "sport_event_status": {
                        "status": "ended",
                        "winner_id": "sr:competitor:a",
                        "winning_reason": reason,
                    },
                    "timeline": [
                        {
                            "id": 1,
                            "type": "match_started",
                            "time": "2026-09-14T17:00:00+00:00",
                        }
                    ],
                },
            },
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


@pytest.mark.parametrize(
    ("reason", "expected_status"),
    (("walkover", "WALKOVER"), ("defaulted", "DEFAULTED")),
)
def test_provider_terminal_reason_maps_to_primary_exclusion_status(
    reason: str,
    expected_status: str,
) -> None:
    prediction = {
        "match_id": "pilot-match-terminal",
        "player_a_id": "canonical-a",
        "player_b_id": "canonical-b",
    }

    winner, status, actual_start = pilot._parse_settlement_evidence(
        _settlement_payload(reason),
        prediction=prediction,
    )

    assert winner == "canonical-a"
    assert status == expected_status
    assert actual_start == "2026-09-14T17:00:00+00:00"
    assert status != "COMPLETED"
