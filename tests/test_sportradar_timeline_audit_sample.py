from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tennis_genome.research_workbench.sportradar_season_inventory import (
    build_sportradar_season_inventory,
)
from tennis_genome.research_workbench.sportradar_season_summaries_census import (
    SeasonSummariesCensus,
    SeasonSummariesCensusRow,
)
from tennis_genome.research_workbench.sportradar_timeline_audit_sample import (
    build_timeline_audit_sample_plan,
    classify_timeline_quality_pilot,
)

GENERATED = "2026-09-16T18:30:00+00:00"


def _write(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def _competition(
    competition_id: str,
    name: str,
    category_id: str,
    category_name: str,
    level: str,
) -> dict[str, object]:
    return {
        "id": competition_id,
        "name": name,
        "type": "singles",
        "level": level,
        "category": {"id": category_id, "name": category_name},
    }


def _season(
    season_id: str,
    competition_id: str,
    name: str,
    start_date: str,
    end_date: str,
) -> dict[str, object]:
    return {
        "id": season_id,
        "competition_id": competition_id,
        "name": name,
        "start_date": start_date,
        "end_date": end_date,
        "year": start_date[:4],
    }


def _inventory(tmp_path: Path):
    atp_competitions = [
        _competition("sr:competition:10", "ATP Tour", "sr:category:3", "ATP", "atp_250"),
        _competition("sr:competition:11", "ATP Masters", "sr:category:3", "ATP", "atp_1000"),
    ]
    wta_competitions = [
        _competition("sr:competition:20", "WTA Tour", "sr:category:6", "WTA", "wta_250"),
        _competition("sr:competition:21", "WTA 1000", "sr:category:6", "WTA", "wta_1000"),
    ]
    atp_path = _write(
        tmp_path / "atp.json",
        {"generated_at": GENERATED, "competitions": atp_competitions},
    )
    wta_path = _write(
        tmp_path / "wta.json",
        {"generated_at": GENERATED, "competitions": wta_competitions},
    )
    season_paths: dict[str, Path] = {}
    definitions = {
        "sr:competition:10": [
            _season("sr:season:101", "sr:competition:10", "ATP Old", "2017-01-01", "2017-02-01"),
            _season("sr:season:102", "sr:competition:10", "ATP Mid", "2021-01-01", "2021-02-01"),
            _season("sr:season:103", "sr:competition:10", "ATP Recent", "2025-01-01", "2025-02-01"),
        ],
        "sr:competition:11": [
            _season("sr:season:104", "sr:competition:11", "ATP Elite", "2024-03-01", "2024-03-15"),
        ],
        "sr:competition:20": [
            _season("sr:season:201", "sr:competition:20", "WTA Old", "2017-01-01", "2017-02-01"),
            _season("sr:season:202", "sr:competition:20", "WTA Mid", "2021-01-01", "2021-02-01"),
            _season("sr:season:203", "sr:competition:20", "WTA Recent", "2025-01-01", "2025-02-01"),
        ],
        "sr:competition:21": [
            _season("sr:season:204", "sr:competition:21", "WTA Elite", "2024-03-01", "2024-03-15"),
        ],
    }
    for competition_id, seasons in definitions.items():
        path = tmp_path / f"{competition_id.replace(':', '_')}.json"
        season_paths[competition_id] = _write(
            path, {"generated_at": GENERATED, "seasons": seasons}
        )
    return build_sportradar_season_inventory(
        atp_competitions_path=atp_path,
        wta_competitions_path=wta_path,
        season_response_paths=season_paths,
        snapshot_at=datetime(2026, 9, 16, 18, 31, tzinfo=UTC),
    )


def _census(inventory, costs: dict[str, int]) -> SeasonSummariesCensus:
    rows = []
    for season in inventory.season_rows:
        if season.status != "HISTORICAL_CANDIDATE":
            continue
        cost = costs[season.season_id]
        rows.append(
            SeasonSummariesCensusRow(
                tour=season.tour,
                competition_id=season.competition_id,
                season_id=season.season_id,
                disposition="SUMMARIES_CAPTURED",
                page_count=1,
                raw_summary_count=cost,
                played_terminal_count=cost,
                walkover_count=0,
                nonterminal_count=0,
                required_timeline_count=cost,
                required_timeline_event_ids=tuple(
                    f"sr:sport_event:{season.season_id.split(':')[-1]}-{index}"
                    for index in range(cost)
                ),
                season_summaries_sha256=(season.season_id.split(":")[-1][0] * 64),
                access_failure_semantic_sha256=None,
            )
        )
    return SeasonSummariesCensus(
        inventory_semantic_sha256=inventory.semantic_sha256,
        inventory_snapshot_at=inventory.snapshot_at,
        access_level="trial",
        historical_candidate_count=inventory.historical_candidate_count,
        summaries_captured_count=len(rows),
        history_not_available_count=0,
        provider_request_count=len(rows),
        total_raw_summary_count=sum(row.raw_summary_count for row in rows),
        total_played_terminal_count=sum(row.played_terminal_count for row in rows),
        total_walkover_count=0,
        total_nonterminal_count=0,
        total_required_timeline_count=sum(row.required_timeline_count for row in rows),
        rows=tuple(rows),
    )


def test_sample_plan_is_deterministic_balanced_and_within_budget(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path)
    costs = {
        "sr:season:101": 8,
        "sr:season:102": 9,
        "sr:season:103": 10,
        "sr:season:104": 11,
        "sr:season:201": 8,
        "sr:season:202": 9,
        "sr:season:203": 10,
        "sr:season:204": 11,
    }
    census = _census(inventory, costs)
    content = json.dumps(inventory.canonical_payload(), sort_keys=True).encode("utf-8")

    first = build_timeline_audit_sample_plan(
        inventory_content=content,
        census=census,
        request_budget_cap=60,
        max_seasons=8,
    )
    second = build_timeline_audit_sample_plan(
        inventory_content=content,
        census=census,
        request_budget_cap=60,
        max_seasons=8,
    )

    assert first.semantic_sha256 == second.semantic_sha256
    assert first.selected_timeline_count <= 60
    assert first.selected_season_count == len(first.selected_rows)
    assert set(first.covered_tour_era_strata) == {
        "ATP:OLD",
        "ATP:MID",
        "ATP:RECENT",
        "WTA:OLD",
        "WTA:MID",
        "WTA:RECENT",
    }
    assert {row.tour for row in first.selected_rows} == {"ATP", "WTA"}
    assert {row.level_family for row in first.selected_rows} >= {"ELITE", "TOUR"}


def test_sample_plan_never_uses_timeline_quality_and_fails_when_nothing_fits(
    tmp_path: Path,
) -> None:
    inventory = _inventory(tmp_path)
    costs = {season.season_id: 20 for season in inventory.season_rows}
    census = _census(inventory, costs)
    content = json.dumps(inventory.canonical_payload(), sort_keys=True).encode("utf-8")

    with pytest.raises(ValueError, match="no complete historical season fits"):
        build_timeline_audit_sample_plan(
            inventory_content=content,
            census=census,
            request_budget_cap=10,
            max_seasons=8,
        )


def test_pilot_quality_classification_is_preregistered() -> None:
    assert (
        classify_timeline_quality_pilot(
            exact_match_started_count=95,
            played_terminal_count=100,
            conflicting_match_started_count=0,
            invalid_match_started_time_count=0,
        )
        == "PILOT_PROMISING"
    )
    assert (
        classify_timeline_quality_pilot(
            exact_match_started_count=95,
            played_terminal_count=100,
            conflicting_match_started_count=1,
            invalid_match_started_time_count=0,
        )
        == "PILOT_MIXED"
    )
    assert (
        classify_timeline_quality_pilot(
            exact_match_started_count=85,
            played_terminal_count=100,
            conflicting_match_started_count=0,
            invalid_match_started_time_count=0,
        )
        == "PILOT_MIXED"
    )
    assert (
        classify_timeline_quality_pilot(
            exact_match_started_count=79,
            played_terminal_count=100,
            conflicting_match_started_count=0,
            invalid_match_started_time_count=0,
        )
        == "PILOT_POOR"
    )
