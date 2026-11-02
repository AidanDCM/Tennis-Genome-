from __future__ import annotations

import pytest

from scripts.adjudicate_api_tennis_official_stats import adjudicate_row


def _case() -> tuple[dict, dict]:
    row = {
        "event_key": 123,
        "event_date": "2026-05-21",
        "event_status": "Finished",
        "event_type_type": "Wta Singles",
        "first_player_key": 1,
        "second_player_key": 2,
        "event_first_player": "A. One",
        "event_second_player": "B. Two",
        "statistics": [
            {
                "player_key": 1,
                "stat_period": "match",
                "stat_type": "Points",
                "stat_name": "Service Points Won",
                "stat_won": 43,
                "stat_total": 80,
            },
            {
                "player_key": 2,
                "stat_period": "match",
                "stat_type": "Points",
                "stat_name": "Service Points Won",
                "stat_won": 36,
                "stat_total": 76,
            },
        ],
    }
    reference = {
        "event_key": 123,
        "event_date": "2026-05-21",
        "tour_event_type": "Wta Singles",
        "official_url": "https://www.wtatennis.com/tournaments/example/scores/LS005",
        "players": [
            {
                "provider_player_key": 1,
                "provider_player_name": "A. One",
                "official_service_points_won": 43,
                "official_service_points_total": 80,
            },
            {
                "provider_player_key": 2,
                "provider_player_name": "B. Two",
                "official_service_points_won": 36,
                "official_service_points_total": 76,
            },
        ],
    }
    return row, reference


def test_official_adjudication_detects_changed_denominator() -> None:
    row, reference = _case()
    checked = adjudicate_row(row, reference)
    assert checked["official_point_agreement"] is True
    assert checked["source_admission"] == "RESEARCH_ONLY"

    row["statistics"][0]["stat_total"] = 79
    changed = adjudicate_row(row, reference)
    assert changed["official_point_agreement"] is False
    assert changed["players"][0]["total_delta"] == -1


def test_official_adjudication_rejects_wrong_identity_and_duplicate_stats() -> None:
    row, reference = _case()
    reference["players"][0]["provider_player_key"] = 3
    with pytest.raises(ValueError, match="identity"):
        adjudicate_row(row, reference)

    row, reference = _case()
    row["statistics"].append(dict(row["statistics"][0]))
    with pytest.raises(ValueError, match="duplicated"):
        adjudicate_row(row, reference)

    row, reference = _case()
    reference["official_url"] = "https://www.wtatennis.com.evil.test/match"
    with pytest.raises(ValueError, match="official match"):
        adjudicate_row(row, reference)

    row, reference = _case()
    reference["official_url"] = "https://nationalbankopen.com/matches-players/results/2026/example"
    assert adjudicate_row(row, reference)["official_point_agreement"] is True

    row, reference = _case()
    reference["official_url"] = "https://www.tennistv.com/videos/example"
    assert adjudicate_row(row, reference)["official_point_agreement"] is True

    row, reference = _case()
    reference["official_url"] = "https://www.usopen.org/en_US/scores/stats/1211.html"
    assert adjudicate_row(row, reference)["official_point_agreement"] is True
