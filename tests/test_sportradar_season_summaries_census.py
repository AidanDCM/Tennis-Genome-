from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tennis_genome.research_workbench.sportradar_season_inventory import (
    build_sportradar_season_inventory,
)
from tennis_genome.research_workbench.sportradar_season_summaries_census import (
    ProviderHttpResponse,
    capture_season_summaries_census,
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
) -> dict[str, object]:
    return {
        "id": competition_id,
        "name": name,
        "type": "singles",
        "category": {"id": category_id, "name": category_name},
    }


def _season(
    season_id: str,
    competition_id: str,
    name: str,
) -> dict[str, object]:
    return {
        "id": season_id,
        "competition_id": competition_id,
        "name": name,
        "start_date": "2026-08-01",
        "end_date": "2026-09-01",
        "year": "2026",
    }


def _inventory_path(tmp_path: Path) -> Path:
    atp_comp = _write(
        tmp_path / "atp.json",
        {
            "generated_at": GENERATED,
            "competitions": [
                _competition("sr:competition:10", "ATP Test", "sr:category:3", "ATP")
            ],
        },
    )
    wta_comp = _write(
        tmp_path / "wta.json",
        {
            "generated_at": GENERATED,
            "competitions": [
                _competition("sr:competition:20", "WTA Test", "sr:category:6", "WTA")
            ],
        },
    )
    atp_seasons = _write(
        tmp_path / "atp-seasons.json",
        {
            "generated_at": GENERATED,
            "seasons": [
                _season("sr:season:100", "sr:competition:10", "ATP Test 2026")
            ],
        },
    )
    wta_seasons = _write(
        tmp_path / "wta-seasons.json",
        {
            "generated_at": GENERATED,
            "seasons": [
                _season("sr:season:200", "sr:competition:20", "WTA Test 2026")
            ],
        },
    )
    inventory = build_sportradar_season_inventory(
        atp_competitions_path=atp_comp,
        wta_competitions_path=wta_comp,
        season_response_paths={
            "sr:competition:10": atp_seasons,
            "sr:competition:20": wta_seasons,
        },
        snapshot_at=datetime(2026, 9, 16, 18, 31, tzinfo=UTC),
    )
    path = tmp_path / "inventory.json"
    path.write_text(
        json.dumps(inventory.canonical_payload(), sort_keys=True), encoding="utf-8"
    )
    return path


def _summary(
    event_id: str,
    *,
    status: str,
    winning_reason: str | None = None,
) -> dict[str, object]:
    sport_event_status: dict[str, object] = {"status": status}
    if winning_reason is not None:
        sport_event_status["winning_reason"] = winning_reason
    return {
        "sport_event": {
            "id": event_id,
            "start_time": "2026-08-10T15:00:00+00:00",
            "sport_event_context": {
                "category": {"id": "sr:category:3", "name": "ATP"},
                "competition": {
                    "id": "sr:competition:10",
                    "name": "ATP Test",
                    "type": "singles",
                },
                "season": {
                    "id": "sr:season:100",
                    "competition_id": "sr:competition:10",
                    "start_date": "2026-08-01",
                },
            },
        },
        "sport_event_status": sport_event_status,
    }


def _page_response() -> ProviderHttpResponse:
    summaries = [
        _summary("sr:sport_event:1", status="closed"),
        _summary("sr:sport_event:2", status="ended", winning_reason="walkover"),
        _summary("sr:sport_event:3", status="not_started"),
    ]
    return ProviderHttpResponse(
        status=200,
        body=json.dumps(
            {"generated_at": GENERATED, "summaries": summaries}, sort_keys=True
        ).encode("utf-8"),
        headers=(
            ("X-Max-Results", "3"),
            ("X-Offset", "0"),
            ("X-Result", "3"),
        ),
    )


def _not_found() -> ProviderHttpResponse:
    return ProviderHttpResponse(
        status=404,
        body=b'{"message":"not found"}',
        headers=(("content-type", "application/json"),),
    )


def test_census_counts_exact_timeline_request_budget_and_access_failure(
    tmp_path: Path,
) -> None:
    responses = [_page_response(), _not_found()]
    sleeps: list[float] = []

    census = capture_season_summaries_census(
        inventory_path=_inventory_path(tmp_path),
        output_dir=tmp_path / "census",
        access_level="trial",
        api_key="secret",
        provider_get=lambda _url, _headers: responses.pop(0),
        sleeper=sleeps.append,
        now=lambda: datetime(2026, 9, 16, 18, 40, tzinfo=UTC),
    )

    assert census.historical_candidate_count == 2
    assert census.summaries_captured_count == 1
    assert census.history_not_available_count == 1
    assert census.provider_request_count == 2
    assert census.total_raw_summary_count == 3
    assert census.total_played_terminal_count == 1
    assert census.total_walkover_count == 1
    assert census.total_nonterminal_count == 1
    assert census.total_required_timeline_count == 1
    assert len(sleeps) == 1
    atp = census.rows[0]
    assert atp.season_id == "sr:season:100"
    assert atp.required_timeline_event_ids == ("sr:sport_event:1",)
    assert atp.season_summaries_sha256 is not None
    wta = census.rows[1]
    assert wta.disposition == "HISTORY_NOT_AVAILABLE"
    assert wta.access_failure_semantic_sha256 is not None
    assert (tmp_path / "census" / "manifest.json").is_file()


def test_census_rejects_auth_failure_instead_of_finalizing_negative_evidence(
    tmp_path: Path,
) -> None:
    forbidden = ProviderHttpResponse(
        status=403,
        body=b"Authentication Error",
        headers=(("content-type", "text/html"),),
    )

    with pytest.raises(RuntimeError, match="authentication/authorization"):
        capture_season_summaries_census(
            inventory_path=_inventory_path(tmp_path),
            output_dir=tmp_path / "census",
            access_level="trial",
            api_key="secret",
            provider_get=lambda _url, _headers: forbidden,
            sleeper=lambda _seconds: None,
            now=lambda: datetime(2026, 9, 16, 18, 40, tzinfo=UTC),
        )


def test_census_rejects_nonempty_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "census"
    output.mkdir()
    (output / "existing").write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="must begin empty"):
        capture_season_summaries_census(
            inventory_path=_inventory_path(tmp_path),
            output_dir=output,
            access_level="trial",
            api_key="secret",
            provider_get=lambda _url, _headers: _page_response(),
            sleeper=lambda _seconds: None,
            now=lambda: datetime(2026, 9, 16, 18, 40, tzinfo=UTC),
        )
