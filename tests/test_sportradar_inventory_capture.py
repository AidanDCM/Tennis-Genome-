from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tennis_genome.research_workbench.sportradar_inventory_capture import (
    ProviderHttpResponse,
    capture_historical_season_inventory,
)

GENERATED = "2026-09-16T18:30:00+00:00"


def _response(payload: dict[str, object]) -> ProviderHttpResponse:
    return ProviderHttpResponse(
        status=200,
        body=json.dumps(payload, sort_keys=True).encode("utf-8"),
        headers=(("content-type", "application/json"),),
    )


def _competition(
    *,
    competition_id: str,
    name: str,
    category_id: str,
    category_name: str,
    competition_type: str,
) -> dict[str, object]:
    return {
        "id": competition_id,
        "name": name,
        "type": competition_type,
        "category": {"id": category_id, "name": category_name},
    }


def _season(
    *,
    season_id: str,
    competition_id: str,
    name: str,
    start: str,
    end: str,
) -> dict[str, object]:
    return {
        "id": season_id,
        "competition_id": competition_id,
        "name": name,
        "start_date": start,
        "end_date": end,
        "year": start[:4],
    }


def _responses() -> list[ProviderHttpResponse]:
    return [
        _response(
            {
                "generated_at": GENERATED,
                "competitions": [
                    _competition(
                        competition_id="sr:competition:10",
                        name="ATP Singles",
                        category_id="sr:category:3",
                        category_name="ATP",
                        competition_type="singles",
                    ),
                    _competition(
                        competition_id="sr:competition:11",
                        name="ATP Doubles",
                        category_id="sr:category:3",
                        category_name="ATP",
                        competition_type="doubles",
                    ),
                ],
            }
        ),
        _response(
            {
                "generated_at": GENERATED,
                "competitions": [
                    _competition(
                        competition_id="sr:competition:20",
                        name="WTA Singles",
                        category_id="sr:category:6",
                        category_name="WTA",
                        competition_type="singles",
                    )
                ],
            }
        ),
        _response(
            {
                "generated_at": GENERATED,
                "seasons": [
                    _season(
                        season_id="sr:season:100",
                        competition_id="sr:competition:10",
                        name="ATP Singles 2026",
                        start="2026-08-01",
                        end="2026-09-01",
                    )
                ],
            }
        ),
        _response(
            {
                "generated_at": GENERATED,
                "seasons": [
                    _season(
                        season_id="sr:season:200",
                        competition_id="sr:competition:20",
                        name="WTA Singles 2026",
                        start="2026-09-10",
                        end="2026-09-20",
                    )
                ],
            }
        ),
    ]


def test_capture_historical_inventory_freezes_complete_singles_denominator(
    tmp_path: Path,
) -> None:
    responses = _responses()
    requested: list[str] = []
    sleeps: list[float] = []

    def provider_get(url: str, headers: dict[str, str]) -> ProviderHttpResponse:
        requested.append(url)
        assert headers["x-api-key"] == "secret"
        return responses.pop(0)

    receipt = capture_historical_season_inventory(
        output_dir=tmp_path / "capture",
        access_level="trial",
        api_key="secret",
        provider_get=provider_get,
        sleeper=sleeps.append,
        now=lambda: datetime(2026, 9, 16, 18, 31, tzinfo=UTC),
    )

    assert receipt.raw_request_count == 4
    assert receipt.singles_competition_count == 2
    assert len(receipt.raw_evidence) == 4
    assert len(requested) == 4
    assert len(sleeps) == 3
    assert all(value >= 1.0 for value in sleeps)
    assert "categories/sr%3Acategory%3A3/competitions.json" in requested[0]
    assert "categories/sr%3Acategory%3A6/competitions.json" in requested[1]
    assert "competitions/sr%3Acompetition%3A10/seasons.json" in requested[2]
    assert "competitions/sr%3Acompetition%3A20/seasons.json" in requested[3]

    inventory = json.loads(
        (tmp_path / "capture" / "inventory.json").read_text(encoding="utf-8")
    )
    assert inventory["historical_candidate_count"] == 1
    assert inventory["not_yet_historical_count"] == 1
    assert inventory["required_singles_competition_count"] == 2
    assert inventory["non_singles_competition_count"] == 1
    assert (tmp_path / "capture" / "manifest.json").is_file()
    assert (tmp_path / "capture" / "capture-receipt.json").is_file()


def test_capture_historical_inventory_rejects_nonempty_target(tmp_path: Path) -> None:
    output = tmp_path / "capture"
    output.mkdir()
    (output / "existing.txt").write_text("do not overwrite", encoding="utf-8")

    with pytest.raises(ValueError, match="must begin empty"):
        capture_historical_season_inventory(
            output_dir=output,
            access_level="trial",
            api_key="secret",
            provider_get=lambda _url, _headers: _responses()[0],
            sleeper=lambda _seconds: None,
            now=lambda: datetime(2026, 9, 16, 18, 31, tzinfo=UTC),
        )


def test_capture_historical_inventory_rejects_category_drift(tmp_path: Path) -> None:
    responses = _responses()
    atp = json.loads(responses[0].body)
    atp["competitions"][0]["category"]["id"] = "sr:category:6"
    responses[0] = _response(atp)

    with pytest.raises(ValueError, match="category ID drifted"):
        capture_historical_season_inventory(
            output_dir=tmp_path / "capture",
            access_level="trial",
            api_key="secret",
            provider_get=lambda _url, _headers: responses.pop(0),
            sleeper=lambda _seconds: None,
            now=lambda: datetime(2026, 9, 16, 18, 31, tzinfo=UTC),
        )
