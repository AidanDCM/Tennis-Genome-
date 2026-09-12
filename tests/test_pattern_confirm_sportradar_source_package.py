from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, MatchStats, PreMatchState
from tennis_genome.experiments.pattern_confirm_live_identity import (
    build_identity_mapping,
    parse_sportradar_prematch_event,
)
from tennis_genome.experiments.pattern_confirm_production import (
    verify_core_artifact,
    verify_profile_artifact,
)
from tennis_genome.experiments.pattern_confirm_sportradar_crosswalk import (
    crosswalk_as_dict,
    seal_crosswalk,
)
from tennis_genome.experiments.pattern_confirm_sportradar_pipeline import (
    training_population_hash,
)
from tennis_genome.experiments.pattern_confirm_sportradar_source_package import (
    build_live_source_package,
    source_package_as_dict,
    verify_source_package,
)

ROOT = Path(__file__).resolve().parents[1]


def _profile():
    return verify_profile_artifact(
        json.loads((ROOT / "research/installment_01/profile_production_001.json").read_text())
    )


def _core():
    return verify_core_artifact(
        json.loads((ROOT / "research/installment_01/core_production_001.json").read_text())
    )


def _pre(match_id: str, when: date, a: str, b: str, order: int) -> PreMatchState:
    return PreMatchState(
        match_id=match_id,
        tour="ATP",
        event_date=when,
        source_order=order,
        tournament_id="base",
        tournament_name="Base Open",
        tournament_level="A",
        surface="Hard",
        round="R32",
        best_of=3,
        player_a_id=a,
        player_b_id=b,
        player_a_name=a,
        player_b_name=b,
        rank_a=None,
        rank_b=None,
        rank_points_a=None,
        rank_points_b=None,
        hand_a="R",
        hand_b="R",
        height_cm_a=185,
        height_cm_b=188,
        age_years_a=25.0,
        age_years_b=26.0,
        ioc_a="USA",
        ioc_b="USA",
    )


def _match(match_id: str, when: date, a: str, b: str, order: int, won: bool) -> HistoricalMatch:
    return HistoricalMatch(
        pre_match=_pre(match_id, when, a, b, order),
        outcome=MatchOutcome(
            match_id=match_id,
            a_won=won,
            score=None,
            retirement=False,
            walkover=False,
        ),
        stats=MatchStats(
            match_id=match_id,
            service_points_a=60,
            service_points_b=58,
            first_serve_points_won_a=28,
            second_serve_points_won_a=14,
            first_serve_points_won_b=25,
            second_serve_points_won_b=13,
            duration_minutes=90,
        ),
    )


def _base():
    return [
        _match("b1", date(2025, 1, 2), "A", "C", 1, True),
        _match("b2", date(2025, 2, 3), "B", "C", 2, False),
    ]


def _models(base: list[HistoricalMatch]):
    row_hash = training_population_hash(base)
    return (
        replace(_profile(), training_n=len(base), training_rows_sha256=row_hash),
        replace(_core(), training_n=len(base), training_rows_sha256=row_hash),
    )


def _event(
    *,
    event_id: str,
    season_id: str,
    season_start: str,
    status: str,
    winner_id: str | None = None,
) -> dict[str, object]:
    event_status: dict[str, object] = {"status": status}
    if winner_id is not None:
        event_status["winner_id"] = winner_id
    return {
        "sport_event": {
            "id": event_id,
            "start_time": "2026-01-05T17:00:00+00:00",
            "start_time_confirmed": True,
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
                    "name": "ATP Test 2026",
                    "start_date": season_start,
                    "end_date": "2026-01-10",
                    "competition_id": "sr:competition:55",
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
                    "virtual": False,
                },
                {
                    "id": "sr:competitor:22",
                    "name": "Player B",
                    "qualifier": "away",
                    "country_code": "USA",
                    "virtual": False,
                },
            ],
        },
        "sport_event_status": event_status,
    }


def _target_setup():
    summary = _event(
        event_id="sr:sport_event:target",
        season_id="sr:season:target",
        season_start="2026-01-02",
        status="not_started",
    )
    parsed = parse_sportradar_prematch_event(summary)
    mapping = build_identity_mapping(
        market_event_id="odds-target",
        market_player_a_name="Player A",
        market_player_b_name="Player B",
        player_a_canonical_id="A",
        player_b_canonical_id="B",
        sportradar_event=parsed,
        method="EXPLICIT_CROSSWALK",
        created_at="2026-01-01T12:00:00+00:00",
    )
    return mapping, summary


def test_source_package_fetches_only_prior_state_and_target_prematch_sources() -> None:
    base = _base()
    profile, core = _models(base)
    mapping, target_summary = _target_setup()
    crosswalk = crosswalk_as_dict(
        seal_crosswalk(
            {
                "sr:competitor:11": "A",
                "sr:competitor:22": "B",
            }
        )
    )
    prior = _event(
        event_id="sr:sport_event:prior",
        season_id="sr:season:prior",
        season_start="2026-01-01",
        status="closed",
        winner_id="sr:competitor:11",
    )
    season_info = {
        "season": {
            "id": mapping.season_id,
            "competition_id": mapping.competition_id,
            "competition": {
                "id": mapping.competition_id,
                "name": mapping.competition_name,
                "type": "singles",
                "level": "atp_250",
            },
            "info": {"surface": "hard", "number_of_competitors": 32},
        }
    }
    profile_a = {
        "competitor": {"id": mapping.player_a_sportradar_id, "country_code": "USA"},
        "info": {"date_of_birth": "1998-01-01", "handedness": "right", "height": 185},
    }
    profile_b = {
        "competitor": {"id": mapping.player_b_sportradar_id, "country_code": "USA"},
        "info": {"date_of_birth": "1997-01-01", "handedness": "right", "height": 188},
    }
    calls: list[str] = []

    def get_json(url: str, *, headers: dict[str, str]) -> object:
        calls.append(url)
        assert headers == {"x-api-key": "secret"}
        if "/sport_events/" in url:
            return target_summary
        if "/seasons/" in url:
            return season_info
        if f"/competitors/{mapping.player_a_sportradar_id}/" in url:
            return profile_a
        if f"/competitors/{mapping.player_b_sportradar_id}/" in url:
            return profile_b
        if "/schedules/2026-01-01/" in url:
            return {"summaries": [prior]}
        raise AssertionError(f"unexpected provider request: {url}")

    package = build_live_source_package(
        match_id="future-1",
        base_history=base,
        identity_mapping=mapping,
        crosswalk_payload=crosswalk,
        profile_artifact=profile,
        core_artifact=core,
        api_key="secret",
        access_level="trial",
        captured_at=datetime(2026, 1, 1, 15, tzinfo=UTC),
        get_json=get_json,
    )
    assert package.match_id == "future-1"
    assert package.state_source_count == 1
    assert package.state_accepted_count == 1
    assert package.state_excluded_count == 0
    assert package.prospective_state["match_id"] == "future-1"
    assert package.prospective_state["history_n"] == 3
    assert all("timeline" not in url for url in calls)
    assert all("result" not in url for url in calls)
    assert len([url for url in calls if "/schedules/" in url]) == 1
    verified = verify_source_package(source_package_as_dict(package))
    assert verified.artifact_sha256 == package.artifact_sha256


def test_source_package_tamper_and_naive_capture_time_fail_closed() -> None:
    payload = {
        "artifact_sha256": "0" * 64,
    }
    with pytest.raises(ValueError, match="digest"):
        verify_source_package(payload)

    base = _base()
    profile, core = _models(base)
    mapping, _ = _target_setup()
    with pytest.raises(ValueError, match="timezone-aware"):
        build_live_source_package(
            match_id="future-1",
            base_history=base,
            identity_mapping=mapping,
            crosswalk_payload=crosswalk_as_dict(
                seal_crosswalk(
                    {
                        "sr:competitor:11": "A",
                        "sr:competitor:22": "B",
                    }
                )
            ),
            profile_artifact=profile,
            core_artifact=core,
            api_key="secret",
            access_level="trial",
            captured_at=datetime(2026, 1, 1, 15),
            get_json=lambda *args, **kwargs: {},
        )
