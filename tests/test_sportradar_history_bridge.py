from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tennis_genome.research_workbench.sportradar_history_bridge import (
    summary_to_historical_match,
)


def _summary(tour_category: str = "sr:category:3") -> dict[str, object]:
    return {
        "sport_event": {
            "id": "sr:sport_event:10",
            "start_time": "2026-06-07T15:00:00-04:00",
            "start_time_confirmed": True,
            "estimated": False,
            "sport_event_context": {
                "category": {"id": tour_category},
                "competition": {
                    "id": "sr:competition:7",
                    "name": "Test",
                    "type": "singles",
                    "level": "atp_250",
                },
                "season": {
                    "id": "sr:season:9",
                    "competition_id": "sr:competition:7",
                    "start_date": "2026-06-01",
                },
                "mode": {"best_of": 3},
            },
            "competitors": [
                {"id": "sr:competitor:20", "qualifier": "home", "name": "Home"},
                {"id": "sr:competitor:21", "qualifier": "away", "name": "Away"},
            ],
        },
        "sport_event_status": {"status": "closed", "winner_id": "sr:competitor:20"},
        "statistics": {
            "totals": {
                "competitors": [
                    {
                        "id": "sr:competitor:20",
                        "qualifier": "home",
                        "statistics": {
                            "service_points_won": 51,
                            "service_points_lost": 40,
                            "first_serve_points_won": 35,
                            "second_serve_points_won": 16,
                        },
                    },
                    {
                        "id": "sr:competitor:21",
                        "qualifier": "away",
                        "statistics": {
                            "service_points_won": 44,
                            "service_points_lost": 47,
                            "first_serve_points_won": 30,
                            "second_serve_points_won": 14,
                        },
                    },
                ]
            }
        },
    }


def _convert(summary: dict[str, object], **kwargs: object):
    inputs = {
        "tour": "ATP",
        "crosswalk": {"sr:competitor:20": "z-player", "sr:competitor:21": "a-player"},
        "surfaces": {"sr:season:9": "Grass"},
        "cutoff_at": datetime(2026, 6, 9, tzinfo=UTC),
        "source_observed_at": datetime(2026, 6, 8, tzinfo=UTC),
        "source_order": 0,
    }
    inputs.update(kwargs)
    return summary_to_historical_match(summary, **inputs)


def test_event_date_and_canonical_orientation_are_independent_of_winner() -> None:
    row = _convert(_summary())
    assert row.pre_match.event_date.isoformat() == "2026-06-07"
    assert row.pre_match.player_a_id == "a-player"
    assert row.pre_match.player_b_id == "z-player"
    assert not row.outcome.a_won
    assert row.stats is not None
    assert row.stats.service_points_a == 91
    assert row.stats.service_points_b == 91
    assert row.stats.first_serve_points_won_a == 30
    assert row.stats.first_serve_points_won_b == 35
    assert row.pre_match.rank_a is None


def test_same_day_and_missing_surface_fail_closed() -> None:
    with pytest.raises(ValueError, match="NOT_PRIOR_TO_CUTOFF"):
        summary_to_historical_match(
            _summary(),
            tour="ATP",
            crosswalk={"sr:competitor:20": "a", "sr:competitor:21": "b"},
            surfaces={"sr:season:9": "Grass"},
            cutoff_at=datetime(2026, 6, 7, 23, tzinfo=UTC),
            source_observed_at=datetime(2026, 6, 7, 20, tzinfo=UTC),
            source_order=0,
        )
    with pytest.raises(ValueError, match="MISSING_SURFACE"):
        _convert(_summary(), surfaces={})


def test_unknown_identity_and_bad_status_fail_closed() -> None:
    with pytest.raises(ValueError, match="MISSING_IDENTITY"):
        _convert(_summary(), crosswalk={})
    summary = _summary()
    summary["sport_event_status"] = {"status": "not_started"}
    with pytest.raises(ValueError, match="NOT_COMPLETED"):
        _convert(summary)


def test_late_source_cannot_be_used_in_historical_replay() -> None:
    with pytest.raises(ValueError, match="SOURCE_AFTER_CUTOFF"):
        _convert(
            _summary(),
            source_observed_at=datetime(2026, 6, 10, tzinfo=UTC),
        )


def test_unconfirmed_scheduled_start_is_excluded() -> None:
    summary = _summary()
    summary["sport_event"]["start_time_confirmed"] = False
    with pytest.raises(ValueError, match="UNCONFIRMED_EVENT_TIME"):
        _convert(summary)


def test_wta_level_uses_existing_frozen_semantics() -> None:
    summary = _summary("sr:category:6")
    summary["sport_event"]["sport_event_context"]["competition"]["level"] = "wta_500"
    row = _convert(summary, tour="WTA")
    assert row.pre_match.tournament_level == "P"
