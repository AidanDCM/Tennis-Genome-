from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tennis_genome.research_workbench.sportradar_season_inventory import (
    SportradarSeasonInventory,
    build_sportradar_season_inventory,
)


def _write(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _competition() -> dict[str, object]:
    return {
        "id": "sr:competition:1",
        "name": "ATP Test",
        "type": "singles",
        "category": {"id": "sr:category:3", "name": "ATP"},
    }


def _season() -> dict[str, object]:
    return {
        "id": "sr:season:1",
        "name": "ATP Test 2026",
        "competition_id": "sr:competition:1",
        "start_date": "2026-01-01",
        "end_date": "2026-01-07",
        "year": "2026",
        "disabled": False,
    }


def _paths(
    root: Path,
    *,
    atp_generated_at: str | None = "2026-09-14T20:00:00Z",
    wta_generated_at: str | None = "2026-09-14T20:00:30Z",
    seasons_generated_at: str | None = "2026-09-14T20:01:00Z",
) -> tuple[Path, Path, Path]:
    atp_payload: dict[str, object] = {"competitions": [_competition()]}
    wta_payload: dict[str, object] = {"competitions": []}
    seasons_payload: dict[str, object] = {"seasons": [_season()]}
    if atp_generated_at is not None:
        atp_payload["generated_at"] = atp_generated_at
    if wta_generated_at is not None:
        wta_payload["generated_at"] = wta_generated_at
    if seasons_generated_at is not None:
        seasons_payload["generated_at"] = seasons_generated_at
    return (
        _write(root / "atp.json", atp_payload),
        _write(root / "wta.json", wta_payload),
        _write(root / "seasons.json", seasons_payload),
    )


def _build(
    root: Path,
    *,
    atp_generated_at: str | None = "2026-09-14T20:00:00Z",
    wta_generated_at: str | None = "2026-09-14T20:00:30Z",
    seasons_generated_at: str | None = "2026-09-14T20:01:00Z",
    asserted_snapshot: datetime = datetime(2026, 9, 14, 23, 59, tzinfo=UTC),
) -> SportradarSeasonInventory:
    atp, wta, seasons = _paths(
        root,
        atp_generated_at=atp_generated_at,
        wta_generated_at=wta_generated_at,
        seasons_generated_at=seasons_generated_at,
    )
    return build_sportradar_season_inventory(
        atp_competitions_path=atp,
        wta_competitions_path=wta,
        season_response_paths={"sr:competition:1": seasons},
        snapshot_at=asserted_snapshot,
    )


def test_snapshot_is_latest_provider_generated_at_not_operator_time(tmp_path: Path) -> None:
    inventory = _build(tmp_path)

    assert inventory.snapshot_at == "2026-09-14T20:01:00+00:00"
    assert inventory.atp_competitions_generated_at == "2026-09-14T20:00:00+00:00"
    assert inventory.wta_competitions_generated_at == "2026-09-14T20:00:30+00:00"
    assert inventory.season_catalogs[0].provider_generated_at == (
        "2026-09-14T20:01:00+00:00"
    )
    assert inventory.historical_candidate_count == 1


@pytest.mark.parametrize(
    "missing",
    ("atp", "wta", "seasons"),
)
def test_every_retained_catalog_requires_generated_at(tmp_path: Path, missing: str) -> None:
    kwargs: dict[str, str | None] = {}
    if missing == "atp":
        kwargs["atp_generated_at"] = None
    elif missing == "wta":
        kwargs["wta_generated_at"] = None
    else:
        kwargs["seasons_generated_at"] = None

    with pytest.raises(ValueError, match="generated_at"):
        _build(tmp_path, **kwargs)


def test_provider_catalogs_crossing_utc_date_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cross UTC dates"):
        _build(
            tmp_path,
            seasons_generated_at="2026-09-15T00:01:00Z",
            asserted_snapshot=datetime(2026, 9, 15, 0, 2, tzinfo=UTC),
        )


def test_operator_snapshot_date_cannot_move_provider_denominator(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must match retained provider generated_at date"):
        _build(
            tmp_path,
            asserted_snapshot=datetime(2026, 9, 13, 23, 59, tzinfo=UTC),
        )


def test_reloaded_inventory_rejects_tampered_snapshot(tmp_path: Path) -> None:
    inventory = _build(tmp_path)
    payload = inventory.canonical_payload()
    payload["snapshot_at"] = "2026-09-14T19:00:00+00:00"

    with pytest.raises(ValueError, match="latest provider generated_at"):
        SportradarSeasonInventory.model_validate(payload)


def test_reloaded_inventory_rejects_cross_date_provider_metadata(tmp_path: Path) -> None:
    inventory = _build(tmp_path)
    payload = inventory.canonical_payload()
    payload["wta_competitions_generated_at"] = "2026-09-15T00:00:01+00:00"

    with pytest.raises(ValueError, match="crosses UTC dates"):
        SportradarSeasonInventory.model_validate(payload)
