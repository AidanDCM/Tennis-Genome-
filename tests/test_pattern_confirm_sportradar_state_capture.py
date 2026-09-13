from __future__ import annotations

from datetime import date

import pytest

from tennis_genome.experiments.pattern_confirm_sportradar_crosswalk import (
    crosswalk_as_dict,
    seal_crosswalk,
)
from tennis_genome.experiments.pattern_confirm_sportradar_state_capture import (
    build_season_state_capture,
    select_state_seasons,
    state_capture_as_dict,
    verify_state_capture,
)


def _competition(
    competition_id: str,
    *,
    category_id: str = "sr:category:3",
    competition_type: str = "singles",
    level: str = "atp_250",
) -> dict[str, object]:
    return {
        "id": competition_id,
        "name": competition_id,
        "type": competition_type,
        "level": level,
        "category": {"id": category_id, "name": "ATP"},
    }


def _season(
    season_id: str,
    competition_id: str,
    start_date: str,
    *,
    disabled: bool = False,
) -> dict[str, object]:
    return {
        "id": season_id,
        "competition_id": competition_id,
        "start_date": start_date,
        "disabled": disabled,
    }


def _summary(
    event_id: str,
    *,
    season_id: str = "sr:season:prior",
    season_start: str = "2026-01-01",
    start_time: str | None = "2026-02-28T23:00:00+00:00",
) -> dict[str, object]:
    sport_event: dict[str, object] = {
        "id": event_id,
        "sport_event_context": {
            "category": {"id": "sr:category:3", "name": "ATP"},
            "competition": {
                "id": "sr:competition:55",
                "name": "ATP Test Men Singles",
                "type": "singles",
                "level": "atp_250",
            },
            "season": {
                "id": season_id,
                "competition_id": "sr:competition:55",
                "start_date": season_start,
            },
            "round": {"name": "round_of_32"},
            "mode": {"best_of": 3},
        },
        "competitors": [
            {
                "id": "sr:competitor:11",
                "name": "Player A",
                "qualifier": "home",
                "country_code": "USA",
            },
            {
                "id": "sr:competitor:22",
                "name": "Player B",
                "qualifier": "away",
                "country_code": "USA",
            },
        ],
    }
    if start_time is not None:
        sport_event["start_time"] = start_time
    return {
        "sport_event": sport_event,
        "sport_event_status": {
            "status": "closed",
            "winner_id": "sr:competitor:11",
        },
    }


def _crosswalk() -> dict[str, object]:
    return crosswalk_as_dict(
        seal_crosswalk(
            {
                "sr:competitor:11": "A",
                "sr:competitor:22": "B",
            }
        )
    )


def test_select_state_seasons_freezes_atp_singles_supported_levels_and_cutoff() -> None:
    competitions = {
        "competitions": [
            _competition("eligible"),
            _competition("wta", category_id="sr:category:6"),
            _competition("doubles", competition_type="doubles"),
            _competition("unsupported", level="challenger"),
        ]
    }
    seasons = {
        "seasons": [
            _season("pre-2026", "eligible", "2025-12-31"),
            _season("keep-a", "eligible", "2026-01-01"),
            _season("disabled", "eligible", "2026-01-10", disabled=True),
            _season("keep-b", "eligible", "2026-02-01"),
            _season("target", "eligible", "2026-03-01"),
            _season("future", "eligible", "2026-04-01"),
            _season("wrong-category", "wta", "2026-01-01"),
            _season("wrong-type", "doubles", "2026-01-01"),
            _season("wrong-level", "unsupported", "2026-01-01"),
        ]
    }
    selected = select_state_seasons(
        competitions,
        seasons,
        target_cutoff_date=date(2026, 3, 1),
    )
    assert [item.season_id for item in selected] == ["keep-a", "keep-b"]


def test_capture_excludes_provider_events_at_or_after_target_cutoff_and_unverified_start() -> None:
    competition = _competition("sr:competition:55")
    season = _season("sr:season:prior", "sr:competition:55", "2026-01-01")
    capture = build_season_state_capture(
        competitions_payload={"competitions": [competition]},
        seasons_payload={"seasons": [season]},
        season_pages={
            "sr:season:prior": [
                (
                    0,
                    {
                        "summaries": [
                            _summary("eligible"),
                            _summary("at-cutoff", start_time="2026-03-01T00:00:00+00:00"),
                            _summary("unverified", start_time=None),
                        ]
                    },
                )
            ]
        },
        target_cutoff_date=date(2026, 3, 1),
        crosswalk_payload=_crosswalk(),
    )
    assert capture.selected_season_count == 1
    assert capture.fetched_page_count == 1
    assert capture.fetched_summary_count == 3
    assert capture.cutoff_eligible_summary_count == 1
    assert capture.cutoff_excluded_summary_count == 2
    assert {item.reason for item in capture.cutoff_exclusions} == {
        "AFTER_TARGET_STATE_CUTOFF",
        "CUTOFF_START_UNVERIFIED",
    }
    assert capture.state_bundle["source_count"] == 1
    assert capture.state_bundle["accepted_count"] == 1
    verified = verify_state_capture(
        state_capture_as_dict(capture),
        crosswalk_payload=_crosswalk(),
    )
    assert verified.artifact_sha256 == capture.artifact_sha256


def test_capture_requires_exact_selected_season_page_set_and_contiguous_offsets() -> None:
    competition = _competition("sr:competition:55")
    season = _season("sr:season:prior", "sr:competition:55", "2026-01-01")
    common = {
        "competitions_payload": {"competitions": [competition]},
        "seasons_payload": {"seasons": [season]},
        "target_cutoff_date": date(2026, 3, 1),
        "crosswalk_payload": _crosswalk(),
    }
    with pytest.raises(ValueError, match="page set"):
        build_season_state_capture(season_pages={}, **common)
    with pytest.raises(ValueError, match="gap or wrong offset"):
        build_season_state_capture(
            season_pages={"sr:season:prior": [(200, {"summaries": []})]},
            **common,
        )


def test_state_capture_tampering_fails_self_hash_verification() -> None:
    capture = build_season_state_capture(
        competitions_payload={"competitions": [_competition("sr:competition:55")]},
        seasons_payload={"seasons": []},
        season_pages={},
        target_cutoff_date=date(2026, 3, 1),
        crosswalk_payload=_crosswalk(),
    )
    payload = state_capture_as_dict(capture)
    payload["fetched_summary_count"] = 99
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_state_capture(payload, crosswalk_payload=_crosswalk())
