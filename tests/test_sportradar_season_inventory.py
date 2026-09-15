from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tennis_genome.research_workbench.sportradar_season_inventory import (
    build_sportradar_season_inventory,
)


def _competition(
    competition_id: str,
    *,
    tour: str,
    competition_type: str = "singles",
    level: str = "atp_250",
) -> dict[str, object]:
    category_id = "sr:category:3" if tour == "ATP" else "sr:category:6"
    return {
        "id": competition_id,
        "name": f"{tour} Test {competition_id}",
        "type": competition_type,
        "level": level,
        "gender": "men" if tour == "ATP" else "women",
        "parent_id": f"parent-{competition_id}",
        "category": {"id": category_id, "name": tour},
    }


def _season(
    season_id: str,
    competition_id: str,
    *,
    start_date: str = "2026-01-01",
    end_date: str = "2026-01-07",
    disabled: bool = False,
) -> dict[str, object]:
    return {
        "id": season_id,
        "name": f"Season {season_id}",
        "competition_id": competition_id,
        "start_date": start_date,
        "end_date": end_date,
        "year": "2026",
        "disabled": disabled,
    }


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _catalog(
    tmp_path: Path, name: str, competitions: list[dict[str, object]]
) -> Path:
    return _write_json(
        tmp_path / f"{name}.json",
        {"generated_at": "2026-09-14T20:00:00Z", "competitions": competitions},
    )


def _seasons(
    tmp_path: Path, name: str, seasons: list[dict[str, object]]
) -> Path:
    return _write_json(
        tmp_path / f"{name}.json",
        {"generated_at": "2026-09-14T20:01:00Z", "seasons": seasons},
    )


def _snapshot() -> datetime:
    return datetime(2026, 9, 14, 20, 5, tzinfo=UTC)


def test_inventory_requires_every_singles_competition_and_keeps_doubles_visible(
    tmp_path: Path,
) -> None:
    atp = _catalog(
        tmp_path,
        "atp",
        [
            _competition("sr:competition:1", tour="ATP", level="atp_250"),
            _competition(
                "sr:competition:2",
                tour="ATP",
                competition_type="doubles",
                level="atp_500",
            ),
        ],
    )
    wta = _catalog(
        tmp_path,
        "wta",
        [_competition("sr:competition:3", tour="WTA", level="wta_1000")],
    )
    atp_seasons = _seasons(
        tmp_path,
        "atp-seasons",
        [_season("sr:season:1", "sr:competition:1")],
    )
    wta_seasons = _seasons(
        tmp_path,
        "wta-seasons",
        [_season("sr:season:3", "sr:competition:3")],
    )

    report = build_sportradar_season_inventory(
        atp_competitions_path=atp,
        wta_competitions_path=wta,
        season_response_paths={
            "sr:competition:1": atp_seasons,
            "sr:competition:3": wta_seasons,
        },
        snapshot_at=_snapshot(),
    )

    assert report.competition_count == 3
    assert report.required_singles_competition_count == 2
    assert report.non_singles_competition_count == 1
    assert report.season_count == 2
    assert report.historical_candidate_count == 2
    doubles = next(
        row
        for row in report.competition_rows
        if row.competition_id.endswith(":2")
    )
    assert doubles.scope == "NON_SINGLES_STRUCTURAL_EXCLUSION"
    selected_levels = {
        row.level
        for row in report.competition_rows
        if row.scope == "SEASON_INVENTORY_REQUIRED"
    }
    assert selected_levels == {"atp_250", "wta_1000"}


def test_missing_or_extra_competition_seasons_evidence_fails_closed(tmp_path: Path) -> None:
    atp = _catalog(
        tmp_path,
        "atp",
        [_competition("sr:competition:1", tour="ATP")],
    )
    wta = _catalog(tmp_path, "wta", [])
    extra = _seasons(tmp_path, "extra", [])

    with pytest.raises(ValueError, match="evidence set mismatch"):
        build_sportradar_season_inventory(
            atp_competitions_path=atp,
            wta_competitions_path=wta,
            season_response_paths={},
            snapshot_at=_snapshot(),
        )
    with pytest.raises(ValueError, match="evidence set mismatch"):
        build_sportradar_season_inventory(
            atp_competitions_path=atp,
            wta_competitions_path=wta,
            season_response_paths={
                "sr:competition:1": _seasons(tmp_path, "one", []),
                "sr:competition:999": extra,
            },
            snapshot_at=_snapshot(),
        )


def test_season_response_cannot_smuggle_another_competition(tmp_path: Path) -> None:
    atp = _catalog(
        tmp_path,
        "atp",
        [_competition("sr:competition:1", tour="ATP")],
    )
    wta = _catalog(tmp_path, "wta", [])
    seasons = _seasons(
        tmp_path,
        "wrong",
        [_season("sr:season:1", "sr:competition:999")],
    )

    with pytest.raises(ValueError, match="another competition"):
        build_sportradar_season_inventory(
            atp_competitions_path=atp,
            wta_competitions_path=wta,
            season_response_paths={"sr:competition:1": seasons},
            snapshot_at=_snapshot(),
        )


def test_duplicate_season_id_across_competitions_is_rejected(tmp_path: Path) -> None:
    atp = _catalog(
        tmp_path,
        "atp",
        [
            _competition("sr:competition:1", tour="ATP"),
            _competition("sr:competition:2", tour="ATP"),
        ],
    )
    wta = _catalog(tmp_path, "wta", [])

    with pytest.raises(ValueError, match="season ID appears more than once"):
        build_sportradar_season_inventory(
            atp_competitions_path=atp,
            wta_competitions_path=wta,
            season_response_paths={
                "sr:competition:1": _seasons(
                    tmp_path,
                    "one",
                    [_season("sr:season:shared", "sr:competition:1")],
                ),
                "sr:competition:2": _seasons(
                    tmp_path,
                    "two",
                    [_season("sr:season:shared", "sr:competition:2")],
                ),
            },
            snapshot_at=_snapshot(),
        )


def test_competition_id_cannot_exist_in_both_tour_catalogs(tmp_path: Path) -> None:
    shared = "sr:competition:1"
    atp = _catalog(tmp_path, "atp", [_competition(shared, tour="ATP")])
    wta = _catalog(
        tmp_path,
        "wta",
        [_competition(shared, tour="WTA", level="wta_250")],
    )
    seasons = _seasons(tmp_path, "shared", [])

    with pytest.raises(ValueError, match="both ATP and WTA"):
        build_sportradar_season_inventory(
            atp_competitions_path=atp,
            wta_competitions_path=wta,
            season_response_paths={shared: seasons},
            snapshot_at=_snapshot(),
        )


def test_disabled_and_active_seasons_are_retained_not_dropped(tmp_path: Path) -> None:
    atp = _catalog(
        tmp_path,
        "atp",
        [_competition("sr:competition:1", tour="ATP")],
    )
    wta = _catalog(tmp_path, "wta", [])
    seasons = _seasons(
        tmp_path,
        "seasons",
        [
            _season(
                "sr:season:historical",
                "sr:competition:1",
                end_date="2026-01-07",
            ),
            _season(
                "sr:season:active",
                "sr:competition:1",
                start_date="2026-09-10",
                end_date="2026-09-20",
            ),
            _season(
                "sr:season:disabled",
                "sr:competition:1",
                end_date="2026-02-01",
                disabled=True,
            ),
        ],
    )

    report = build_sportradar_season_inventory(
        atp_competitions_path=atp,
        wta_competitions_path=wta,
        season_response_paths={"sr:competition:1": seasons},
        snapshot_at=_snapshot(),
    )

    statuses = {row.season_id: row.status for row in report.season_rows}
    assert statuses == {
        "sr:season:historical": "HISTORICAL_CANDIDATE",
        "sr:season:active": "NOT_YET_HISTORICAL",
        "sr:season:disabled": "DISABLED_PROVIDER_SEASON",
    }
    assert report.historical_candidate_count == 1
    assert report.not_yet_historical_count == 1
    assert report.disabled_season_count == 1


def test_end_date_equal_to_snapshot_date_is_not_yet_historical(tmp_path: Path) -> None:
    atp = _catalog(
        tmp_path,
        "atp",
        [_competition("sr:competition:1", tour="ATP")],
    )
    wta = _catalog(tmp_path, "wta", [])
    seasons = _seasons(
        tmp_path,
        "same-day",
        [
            _season(
                "sr:season:1",
                "sr:competition:1",
                start_date="2026-09-10",
                end_date="2026-09-14",
            )
        ],
    )

    report = build_sportradar_season_inventory(
        atp_competitions_path=atp,
        wta_competitions_path=wta,
        season_response_paths={"sr:competition:1": seasons},
        snapshot_at=_snapshot(),
    )
    assert report.season_rows[0].status == "NOT_YET_HISTORICAL"


def test_level_is_metadata_not_an_inventory_selection_rule(tmp_path: Path) -> None:
    atp = _catalog(
        tmp_path,
        "atp",
        [
            _competition(
                "sr:competition:1",
                tour="ATP",
                level="provider_level_not_preselected",
            )
        ],
    )
    wta = _catalog(tmp_path, "wta", [])
    seasons = _seasons(tmp_path, "seasons", [])

    report = build_sportradar_season_inventory(
        atp_competitions_path=atp,
        wta_competitions_path=wta,
        season_response_paths={"sr:competition:1": seasons},
        snapshot_at=_snapshot(),
    )
    assert report.required_singles_competition_count == 1
    assert report.competition_rows[0].level == "provider_level_not_preselected"


def test_category_semantic_drift_is_rejected(tmp_path: Path) -> None:
    broken = _competition("sr:competition:1", tour="ATP")
    category = broken["category"]
    assert isinstance(category, dict)
    category["name"] = "WTA"
    atp = _catalog(tmp_path, "atp", [broken])
    wta = _catalog(tmp_path, "wta", [])

    with pytest.raises(ValueError, match="another category"):
        build_sportradar_season_inventory(
            atp_competitions_path=atp,
            wta_competitions_path=wta,
            season_response_paths={"sr:competition:1": _seasons(tmp_path, "s", [])},
            snapshot_at=_snapshot(),
        )


def test_raw_catalog_byte_change_changes_inventory_identity(tmp_path: Path) -> None:
    atp = _catalog(
        tmp_path,
        "atp",
        [_competition("sr:competition:1", tour="ATP")],
    )
    wta = _catalog(tmp_path, "wta", [])
    seasons = _seasons(tmp_path, "seasons", [])
    first = build_sportradar_season_inventory(
        atp_competitions_path=atp,
        wta_competitions_path=wta,
        season_response_paths={"sr:competition:1": seasons},
        snapshot_at=_snapshot(),
    )

    payload = json.loads(atp.read_text(encoding="utf-8"))
    payload["provider_note"] = "raw byte identity changed"
    atp.write_text(json.dumps(payload), encoding="utf-8")
    changed = build_sportradar_season_inventory(
        atp_competitions_path=atp,
        wta_competitions_path=wta,
        season_response_paths={"sr:competition:1": seasons},
        snapshot_at=_snapshot(),
    )

    assert first.atp_competitions_sha256 != changed.atp_competitions_sha256
    assert first.semantic_sha256 != changed.semantic_sha256
