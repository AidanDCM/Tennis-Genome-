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
from tennis_genome.research_workbench.sportradar_targeted_2026 import (
    capture_targeted_2026,
)

GENERATED = "2026-09-16T18:30:00+00:00"


def _write(path: Path, value: dict[str, object]) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _inventory(tmp_path: Path) -> Path:
    atp = _write(
        tmp_path / "atp.json",
        {
            "generated_at": GENERATED,
            "competitions": [
                {
                    "id": "sr:competition:10",
                    "name": "ATP Test",
                    "type": "singles",
                    "category": {"id": "sr:category:3", "name": "ATP"},
                }
            ],
        },
    )
    wta = _write(tmp_path / "wta.json", {"generated_at": GENERATED, "competitions": []})
    seasons = _write(
        tmp_path / "seasons.json",
        {
            "generated_at": GENERATED,
            "seasons": [
                {
                    "id": "sr:season:100",
                    "competition_id": "sr:competition:10",
                    "name": "ATP Test 2026",
                    "start_date": "2026-08-01",
                    "end_date": "2026-09-01",
                    "year": "2026",
                }
            ],
        },
    )
    inventory = build_sportradar_season_inventory(
        atp_competitions_path=atp,
        wta_competitions_path=wta,
        season_response_paths={"sr:competition:10": seasons},
        snapshot_at=datetime(2026, 9, 16, 18, 31, tzinfo=UTC),
    )
    return _write(tmp_path / "inventory.json", inventory.canonical_payload())


def _summary(event: int) -> dict[str, object]:
    return {
        "sport_event": {
            "id": f"sr:sport_event:{event}",
            "start_time": "2026-08-10T15:00:00+00:00",
            "sport_event_context": {
                "category": {"id": "sr:category:3", "name": "ATP"},
                "competition": {"id": "sr:competition:10", "name": "ATP Test", "type": "singles"},
                "season": {
                    "id": "sr:season:100",
                    "competition_id": "sr:competition:10",
                    "start_date": "2026-08-01",
                },
            },
        },
        "sport_event_status": {"status": "closed"},
    }


def _page(offset: int) -> ProviderHttpResponse:
    return ProviderHttpResponse(
        status=200,
        body=json.dumps({"generated_at": GENERATED, "summaries": [_summary(offset + 1)]}).encode(),
        headers=(("X-Max-Results", "2"), ("X-Offset", str(offset)), ("X-Result", "1")),
    )


def test_mid_season_cap_resumes_without_refetch(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path)
    output = tmp_path / "capture"
    calls: list[str] = []

    def get(url: str, _headers: dict[str, str]) -> ProviderHttpResponse:
        calls.append(url)
        return _page(0 if "start=0" in url else 1)

    first = capture_targeted_2026(
        inventory_path=inventory,
        output_dir=output,
        source_dir=None,
        access_level="trial",
        api_key="secret",
        max_requests=1,
        provider_get=get,
        sleeper=lambda _: None,
    )
    assert first["requests_this_run"] == 1
    assert first["complete_seasons"] == 0
    second = capture_targeted_2026(
        inventory_path=inventory,
        output_dir=output,
        source_dir=None,
        access_level="trial",
        api_key="secret",
        max_requests=1,
        provider_get=get,
        sleeper=lambda _: None,
    )
    assert second["requests_this_run"] == 1
    assert second["complete_seasons"] == 1
    assert len(calls) == 2
    assert "start=0" in calls[0] and "start=1" in calls[1]


def test_zero_budget_and_quota_failure_do_not_retry(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path)
    output = tmp_path / "capture"
    calls = 0

    def get(_url: str, _headers: dict[str, str]) -> ProviderHttpResponse:
        nonlocal calls
        calls += 1
        return ProviderHttpResponse(status=429, body=b"quota", headers=())

    zero = capture_targeted_2026(
        inventory_path=inventory,
        output_dir=output,
        source_dir=None,
        access_level="trial",
        api_key="secret",
        max_requests=0,
        provider_get=get,
    )
    assert zero["requests_this_run"] == 0 and calls == 0
    failed = capture_targeted_2026(
        inventory_path=inventory,
        output_dir=output,
        source_dir=None,
        access_level="trial",
        api_key="secret",
        max_requests=5,
        provider_get=get,
    )
    assert failed["requests_this_run"] == 1 and calls == 1
    assert failed["blocked"] == "sr:season:100: HTTP 429"
    assert not list((output / "seasons" / "sr_season_100").glob("page-*.json"))
