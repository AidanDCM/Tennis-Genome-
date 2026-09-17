from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from tennis_genome.research_workbench.sportradar_season_inventory import (
    build_sportradar_season_inventory,
)
from tennis_genome.research_workbench.sportradar_season_summaries_census import (
    ProviderHttpResponse,
)
from tennis_genome.research_workbench.sportradar_season_summaries_resume import (
    reconstruct_resume_checkpoint,
    resume_season_summaries_census,
)

GENERATED = "2026-09-17T14:00:00+00:00"


def _write(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def _inventory_path(tmp_path: Path) -> Path:
    competitions = _write(
        tmp_path / "atp.json",
        {
            "generated_at": GENERATED,
            "competitions": [
                {
                    "id": "sr:competition:10",
                    "name": "ATP Resume Test",
                    "type": "singles",
                    "level": "atp_250",
                    "category": {"id": "sr:category:3", "name": "ATP"},
                }
            ],
        },
    )
    wta = _write(
        tmp_path / "wta.json",
        {"generated_at": GENERATED, "competitions": []},
    )
    seasons = _write(
        tmp_path / "seasons.json",
        {
            "generated_at": GENERATED,
            "seasons": [
                {
                    "id": "sr:season:100",
                    "competition_id": "sr:competition:10",
                    "name": "ATP Resume Test 2024",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31",
                    "year": "2024",
                },
                {
                    "id": "sr:season:101",
                    "competition_id": "sr:competition:10",
                    "name": "ATP Resume Test 2025",
                    "start_date": "2025-01-01",
                    "end_date": "2025-01-31",
                    "year": "2025",
                },
            ],
        },
    )
    inventory = build_sportradar_season_inventory(
        atp_competitions_path=competitions,
        wta_competitions_path=wta,
        season_response_paths={"sr:competition:10": seasons},
        snapshot_at=datetime(2026, 9, 17, 14, 1, tzinfo=UTC),
    )
    path = tmp_path / "inventory.json"
    path.write_text(
        json.dumps(inventory.canonical_payload(), sort_keys=True), encoding="utf-8"
    )
    return path


def _summary(season_id: str, event_id: str) -> dict[str, object]:
    year = "2024" if season_id.endswith("100") else "2025"
    return {
        "sport_event": {
            "id": event_id,
            "start_time": f"{year}-01-10T12:00:00+00:00",
            "sport_event_context": {
                "category": {"id": "sr:category:3", "name": "ATP"},
                "competition": {
                    "id": "sr:competition:10",
                    "name": "ATP Resume Test",
                    "type": "singles",
                },
                "season": {
                    "id": season_id,
                    "competition_id": "sr:competition:10",
                    "name": f"ATP Resume Test {year}",
                    "start_date": f"{year}-01-01",
                },
            },
        },
        "sport_event_status": {"status": "closed", "winner_id": "sr:competitor:1"},
    }


def _page(season_id: str, event_id: str) -> bytes:
    return json.dumps(
        {"generated_at": GENERATED, "summaries": [_summary(season_id, event_id)]},
        sort_keys=True,
    ).encode("utf-8")


def _headers(status: int, *, count: int = 1) -> bytes:
    if status == 200:
        return (
            f"HTTP/1.1 200\nX-Max-Results: {count}\nX-Offset: 0\nX-Result: {count}\n"
        ).encode("iso-8859-1")
    return f"HTTP/1.1 {status}\nContent-Type: application/json\n".encode(
        "iso-8859-1"
    )


def _build_partial(tmp_path: Path) -> Path:
    root = tmp_path / "partial"
    first = root / "seasons" / "sr_season_100"
    first.mkdir(parents=True)
    (first / "page-000-offset-000000.json").write_bytes(
        _page("sr:season:100", "sr:sport_event:1000")
    )
    (first / "page-000-offset-000000.headers").write_bytes(_headers(200))

    second = root / "seasons" / "sr_season_101"
    second.mkdir(parents=True)
    (second / "page-000-offset-000000.json").write_text(
        '{"message":"Limit Exceeded"}', encoding="utf-8"
    )
    (second / "page-000-offset-000000.headers").write_bytes(_headers(429))
    return root


def test_reconstructs_contiguous_prefix_and_quota_frontier(tmp_path: Path) -> None:
    inventory = _inventory_path(tmp_path)
    partial = _build_partial(tmp_path)

    checkpoint = reconstruct_resume_checkpoint(
        inventory_path=inventory,
        partial_census_root=partial,
    )

    assert checkpoint.completed_candidate_count == 1
    assert checkpoint.next_candidate_index == 1
    assert checkpoint.next_season_id == "sr:season:101"
    assert checkpoint.retained_provider_response_count == 2
    assert checkpoint.reusable_provider_response_count == 1
    assert checkpoint.quota_exhausted is True
    assert checkpoint.quota_failure_status == 429
    assert checkpoint.rows[0].season_id == "sr:season:100"


def test_resume_reuses_completed_prefix_without_querying_it_again(tmp_path: Path) -> None:
    inventory = _inventory_path(tmp_path)
    partial = _build_partial(tmp_path)
    urls: list[str] = []

    def provider_get(url: str, _headers_map: dict[str, str]) -> ProviderHttpResponse:
        urls.append(url)
        assert "sr%3Aseason%3A101" in url
        return ProviderHttpResponse(
            status=200,
            body=_page("sr:season:101", "sr:sport_event:1001"),
            headers=(
                ("X-Max-Results", "1"),
                ("X-Offset", "0"),
                ("X-Result", "1"),
            ),
        )

    census, checkpoint = resume_season_summaries_census(
        inventory_path=inventory,
        partial_census_root=partial,
        output_dir=tmp_path / "resumed",
        access_level="trial",
        api_key="secret",
        provider_get=provider_get,
        sleeper=lambda _seconds: None,
        now=lambda: datetime(2026, 9, 17, 15, 0, tzinfo=UTC),
    )

    assert census is not None
    assert len(urls) == 1
    assert census.historical_candidate_count == 2
    assert len(census.rows) == 2
    assert [row.season_id for row in census.rows] == ["sr:season:100", "sr:season:101"]
    assert census.total_required_timeline_count == 2
    assert checkpoint.completed_candidate_count == 2
    assert checkpoint.next_season_id is None
    assert checkpoint.quota_exhausted is False
