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
from tennis_genome.research_workbench.sportradar_season_summaries_census_v2 import (
    capture_season_summaries_census,
)

GENERATED = "2026-09-16T18:30:00+00:00"


def _write(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def _inventory_path(tmp_path: Path) -> Path:
    atp_comp = _write(
        tmp_path / "atp.json",
        {
            "generated_at": GENERATED,
            "competitions": [
                {
                    "id": "sr:competition:10",
                    "name": "ATP Empty Test",
                    "type": "singles",
                    "category": {"id": "sr:category:3", "name": "ATP"},
                }
            ],
        },
    )
    wta_comp = _write(
        tmp_path / "wta.json",
        {"generated_at": GENERATED, "competitions": []},
    )
    atp_seasons = _write(
        tmp_path / "atp-seasons.json",
        {
            "generated_at": GENERATED,
            "seasons": [
                {
                    "id": "sr:season:100",
                    "competition_id": "sr:competition:10",
                    "name": "ATP Empty Test 2026",
                    "start_date": "2026-08-01",
                    "end_date": "2026-09-01",
                    "year": "2026",
                }
            ],
        },
    )
    inventory = build_sportradar_season_inventory(
        atp_competitions_path=atp_comp,
        wta_competitions_path=wta_comp,
        season_response_paths={"sr:competition:10": atp_seasons},
        snapshot_at=datetime(2026, 9, 16, 18, 31, tzinfo=UTC),
    )
    path = tmp_path / "inventory.json"
    path.write_text(
        json.dumps(inventory.canonical_payload(), sort_keys=True), encoding="utf-8"
    )
    return path


def _empty_page() -> ProviderHttpResponse:
    return ProviderHttpResponse(
        status=200,
        body=json.dumps(
            {"generated_at": GENERATED, "summaries": []}, sort_keys=True
        ).encode("utf-8"),
        headers=(
            ("X-Max-Results", "0"),
            ("X-Offset", "0"),
            ("X-Result", "0"),
        ),
    )


def test_authenticated_zero_row_season_is_retained_as_captured_empty_denominator(
    tmp_path: Path,
) -> None:
    census = capture_season_summaries_census(
        inventory_path=_inventory_path(tmp_path),
        output_dir=tmp_path / "census",
        access_level="trial",
        api_key="secret",
        provider_get=lambda _url, _headers: _empty_page(),
        sleeper=lambda _seconds: None,
        now=lambda: datetime(2026, 9, 16, 18, 40, tzinfo=UTC),
    )

    assert census.historical_candidate_count == 1
    assert census.summaries_captured_count == 1
    assert census.history_not_available_count == 0
    assert census.provider_request_count == 1
    assert census.total_raw_summary_count == 0
    assert census.total_played_terminal_count == 0
    assert census.total_required_timeline_count == 0
    row = census.rows[0]
    assert row.disposition == "SUMMARIES_CAPTURED"
    assert row.page_count == 1
    assert row.raw_summary_count == 0
    assert row.required_timeline_event_ids == ()
    assert row.season_summaries_sha256 is not None
    retained = tmp_path / "census" / "seasons" / "sr_season_100"
    assert any(retained.glob("*.json"))
    assert any(retained.glob("*.headers"))
