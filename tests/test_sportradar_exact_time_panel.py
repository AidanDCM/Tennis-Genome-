from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tennis_genome.research_workbench.sportradar_exact_time_panel import (
    build_exact_time_panel_manifest,
    build_provider_access_failure_evidence,
)
from tennis_genome.research_workbench.sportradar_season_inventory import (
    build_sportradar_season_inventory,
)
from tennis_genome.research_workbench.sportradar_start_time_audit_v2 import (
    audit_sportradar_start_time_coverage_v2,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _competition(competition_id: str, *, tour: str) -> dict[str, object]:
    category_id = "sr:category:3" if tour == "ATP" else "sr:category:6"
    return {
        "id": competition_id,
        "name": f"{tour} Competition {competition_id}",
        "type": "singles",
        "level": "atp_250" if tour == "ATP" else "wta_250",
        "category": {"id": category_id, "name": tour},
    }


def _season(
    season_id: str,
    competition_id: str,
    *,
    start_date: str,
    end_date: str,
    disabled: bool = False,
) -> dict[str, object]:
    return {
        "id": season_id,
        "name": f"Season {season_id}",
        "competition_id": competition_id,
        "start_date": start_date,
        "end_date": end_date,
        "year": start_date[:4],
        "disabled": disabled,
    }


def _inventory(tmp_path: Path):
    atp_competition = "sr:competition:1"
    wta_competition = "sr:competition:2"
    atp_catalog = _write_json(
        tmp_path / "atp.json",
        {
            "generated_at": "2026-09-14T19:00:00Z",
            "competitions": [_competition(atp_competition, tour="ATP")],
        },
    )
    wta_catalog = _write_json(
        tmp_path / "wta.json",
        {
            "generated_at": "2026-09-14T19:00:00Z",
            "competitions": [_competition(wta_competition, tour="WTA")],
        },
    )
    atp_seasons = _write_json(
        tmp_path / "atp-seasons.json",
        {
            "generated_at": "2026-09-14T19:01:00Z",
            "seasons": [
                _season(
                    "sr:season:admit",
                    atp_competition,
                    start_date="2026-01-01",
                    end_date="2026-01-07",
                ),
                _season(
                    "sr:season:fail",
                    atp_competition,
                    start_date="2026-02-01",
                    end_date="2026-02-07",
                ),
                _season(
                    "sr:season:active",
                    atp_competition,
                    start_date="2026-09-10",
                    end_date="2026-09-20",
                ),
            ],
        },
    )
    wta_seasons = _write_json(
        tmp_path / "wta-seasons.json",
        {
            "generated_at": "2026-09-14T19:01:00Z",
            "seasons": [
                _season(
                    "sr:season:access",
                    wta_competition,
                    start_date="2026-03-01",
                    end_date="2026-03-07",
                ),
                _season(
                    "sr:season:disabled",
                    wta_competition,
                    start_date="2026-04-01",
                    end_date="2026-04-07",
                    disabled=True,
                ),
            ],
        },
    )
    inventory = build_sportradar_season_inventory(
        atp_competitions_path=atp_catalog,
        wta_competitions_path=wta_catalog,
        season_response_paths={
            atp_competition: atp_seasons,
            wta_competition: wta_seasons,
        },
        snapshot_at=datetime(2026, 9, 14, 19, 5, tzinfo=UTC),
    )
    content = (json.dumps(inventory.canonical_payload(), sort_keys=True) + "\n").encode()
    return inventory, content


def _summary(
    *,
    season_id: str,
    competition_id: str,
    competition_name: str,
    tour: str,
    event_id: str,
    start_date: str,
) -> dict[str, object]:
    category_id = "sr:category:3" if tour == "ATP" else "sr:category:6"
    return {
        "sport_event": {
            "id": event_id,
            "start_time": f"{start_date}T14:00:00Z",
            "start_time_confirmed": True,
            "estimated": False,
            "sport_event_context": {
                "category": {"id": category_id, "name": tour},
                "competition": {
                    "id": competition_id,
                    "name": competition_name,
                    "type": "singles",
                },
                "season": {
                    "id": season_id,
                    "start_date": start_date,
                    "competition_id": competition_id,
                },
            },
        },
        "sport_event_status": {"status": "closed"},
    }


def _audit_bytes(
    tmp_path: Path,
    *,
    season_id: str,
    competition_id: str,
    competition_name: str,
    tour: str,
    start_date: str,
    has_start: bool,
) -> bytes:
    safe = season_id.rsplit(":", 1)[-1]
    event_id = f"sr:sport_event:{safe}"
    page = tmp_path / f"{safe}-page.json"
    headers = tmp_path / f"{safe}-headers.txt"
    timeline = tmp_path / f"{safe}-timeline.json"
    page.write_text(
        json.dumps(
            {
                "summaries": [
                    _summary(
                        season_id=season_id,
                        competition_id=competition_id,
                        competition_name=competition_name,
                        tour=tour,
                        event_id=event_id,
                        start_date=start_date,
                    )
                ]
            }
        ),
        encoding="utf-8",
    )
    headers.write_text(
        "X-Max-Results: 1\nX-Offset: 0\nX-Result: 1\n",
        encoding="utf-8",
    )
    timeline_payload: dict[str, object] = {
        "sport_event": {"id": event_id},
        "timeline": [],
    }
    if has_start:
        timeline_payload["timeline"] = [
            {"type": "match_started", "time": f"{start_date}T14:03:00Z"}
        ]
    timeline.write_text(json.dumps(timeline_payload), encoding="utf-8")
    audit = audit_sportradar_start_time_coverage_v2(
        page_pairs=((page, headers),), timeline_paths=(timeline,)
    )
    return (json.dumps(audit.canonical_payload(), sort_keys=True) + "\n").encode()


def _access_evidence(tmp_path: Path, inventory):
    row = next(row for row in inventory.season_rows if row.season_id == "sr:season:access")
    headers = tmp_path / "access.headers"
    body = tmp_path / "access.body"
    headers.write_bytes(b"HTTP/1.1 410 Gone\r\nContent-Type: application/json\r\n")
    body.write_bytes(b'{"message":"season history unavailable"}\n')
    return build_provider_access_failure_evidence(
        season=row,
        endpoint_path="seasons/sr:season:access/summaries.json",
        attempted_at=datetime(2026, 9, 14, 19, 10, tzinfo=UTC),
        http_status=410,
        response_headers_path=headers,
        response_body_path=body,
    )


def test_panel_accounts_for_every_historical_candidate_without_dropping_failures(
    tmp_path: Path,
) -> None:
    inventory, inventory_content = _inventory(tmp_path)
    admitted = _audit_bytes(
        tmp_path,
        season_id="sr:season:admit",
        competition_id="sr:competition:1",
        competition_name="ATP Competition sr:competition:1",
        tour="ATP",
        start_date="2026-01-01",
        has_start=True,
    )
    failed = _audit_bytes(
        tmp_path,
        season_id="sr:season:fail",
        competition_id="sr:competition:1",
        competition_name="ATP Competition sr:competition:1",
        tour="ATP",
        start_date="2026-02-01",
        has_start=False,
    )
    access = _access_evidence(tmp_path, inventory)

    manifest = build_exact_time_panel_manifest(
        inventory_content=inventory_content,
        admitted_audits={"sr:season:admit": admitted},
        failed_audits={"sr:season:fail": failed},
        access_failures={"sr:season:access": access},
        repo_root=_repo_root(),
    )

    assert manifest.historical_candidate_count == 3
    assert manifest.chronology_admitted_count == 1
    assert manifest.chronology_failed_count == 1
    assert manifest.access_failure_count == 1
    assert manifest.not_yet_historical_count == 1
    assert manifest.disabled_season_count == 1
    assert manifest.selected_season_ids == ("sr:season:admit",)
    by_id = {row.season_id: row for row in manifest.rows}
    assert by_id["sr:season:admit"].selected_for_exact_time_panel is True
    assert by_id["sr:season:fail"].disposition == "CHRONOLOGY_FAILED"
    assert "MISSING_MATCH_STARTED" in by_id["sr:season:fail"].failure_reasons
    assert by_id["sr:season:access"].disposition == "ACCESS_FAILURE"
    assert by_id["sr:season:active"].disposition == "NOT_YET_HISTORICAL"
    assert by_id["sr:season:disabled"].disposition == "DISABLED_PROVIDER_SEASON"
    assert len(manifest.admitted_receipt_sha256s) == 1


def test_missing_historical_disposition_blocks_panel_finalization(tmp_path: Path) -> None:
    _, inventory_content = _inventory(tmp_path)
    with pytest.raises(ValueError, match="disposition set mismatch"):
        build_exact_time_panel_manifest(
            inventory_content=inventory_content,
            admitted_audits={},
            failed_audits={},
            access_failures={},
            repo_root=_repo_root(),
        )


def test_same_season_cannot_receive_multiple_dispositions(tmp_path: Path) -> None:
    inventory, inventory_content = _inventory(tmp_path)
    admitted = _audit_bytes(
        tmp_path,
        season_id="sr:season:admit",
        competition_id="sr:competition:1",
        competition_name="ATP Competition sr:competition:1",
        tour="ATP",
        start_date="2026-01-01",
        has_start=True,
    )
    with pytest.raises(ValueError, match="multiple chronology dispositions"):
        build_exact_time_panel_manifest(
            inventory_content=inventory_content,
            admitted_audits={"sr:season:admit": admitted},
            failed_audits={"sr:season:admit": admitted},
            access_failures={"sr:season:access": _access_evidence(tmp_path, inventory)},
            repo_root=_repo_root(),
        )


def test_passing_audit_cannot_be_labeled_chronology_failed(tmp_path: Path) -> None:
    inventory, inventory_content = _inventory(tmp_path)
    passing = _audit_bytes(
        tmp_path,
        season_id="sr:season:fail",
        competition_id="sr:competition:1",
        competition_name="ATP Competition sr:competition:1",
        tour="ATP",
        start_date="2026-02-01",
        has_start=True,
    )
    access = _access_evidence(tmp_path, inventory)
    admitted = _audit_bytes(
        tmp_path,
        season_id="sr:season:admit",
        competition_id="sr:competition:1",
        competition_name="ATP Competition sr:competition:1",
        tour="ATP",
        start_date="2026-01-01",
        has_start=True,
    )
    with pytest.raises(ValueError, match="actually passes"):
        build_exact_time_panel_manifest(
            inventory_content=inventory_content,
            admitted_audits={"sr:season:admit": admitted},
            failed_audits={"sr:season:fail": passing},
            access_failures={"sr:season:access": access},
            repo_root=_repo_root(),
        )


def test_tampered_failed_audit_is_invalid_not_negative_evidence(tmp_path: Path) -> None:
    inventory, inventory_content = _inventory(tmp_path)
    admitted = _audit_bytes(
        tmp_path,
        season_id="sr:season:admit",
        competition_id="sr:competition:1",
        competition_name="ATP Competition sr:competition:1",
        tour="ATP",
        start_date="2026-01-01",
        has_start=True,
    )
    failed = _audit_bytes(
        tmp_path,
        season_id="sr:season:fail",
        competition_id="sr:competition:1",
        competition_name="ATP Competition sr:competition:1",
        tour="ATP",
        start_date="2026-02-01",
        has_start=False,
    )
    payload = json.loads(failed)
    payload["base_audit"]["missing_match_started_count"] = 0
    tampered = (json.dumps(payload) + "\n").encode()
    with pytest.raises(ValueError, match="missing-start count does not reproduce"):
        build_exact_time_panel_manifest(
            inventory_content=inventory_content,
            admitted_audits={"sr:season:admit": admitted},
            failed_audits={"sr:season:fail": tampered},
            access_failures={"sr:season:access": _access_evidence(tmp_path, inventory)},
            repo_root=_repo_root(),
        )


def test_audit_identity_must_match_frozen_inventory(tmp_path: Path) -> None:
    inventory, inventory_content = _inventory(tmp_path)
    wrong = _audit_bytes(
        tmp_path,
        season_id="sr:season:admit",
        competition_id="sr:competition:1",
        competition_name="WRONG COMPETITION NAME",
        tour="ATP",
        start_date="2026-01-01",
        has_start=True,
    )
    failed = _audit_bytes(
        tmp_path,
        season_id="sr:season:fail",
        competition_id="sr:competition:1",
        competition_name="ATP Competition sr:competition:1",
        tour="ATP",
        start_date="2026-02-01",
        has_start=False,
    )
    with pytest.raises(ValueError, match="competition name does not match"):
        build_exact_time_panel_manifest(
            inventory_content=inventory_content,
            admitted_audits={"sr:season:admit": wrong},
            failed_audits={"sr:season:fail": failed},
            access_failures={"sr:season:access": _access_evidence(tmp_path, inventory)},
            repo_root=_repo_root(),
        )


def test_active_or_disabled_season_cannot_receive_chronology_evidence(tmp_path: Path) -> None:
    inventory, inventory_content = _inventory(tmp_path)
    active = _audit_bytes(
        tmp_path,
        season_id="sr:season:active",
        competition_id="sr:competition:1",
        competition_name="ATP Competition sr:competition:1",
        tour="ATP",
        start_date="2026-09-10",
        has_start=True,
    )
    with pytest.raises(ValueError, match="extra=.*sr:season:active"):
        build_exact_time_panel_manifest(
            inventory_content=inventory_content,
            admitted_audits={"sr:season:active": active},
            failed_audits={},
            access_failures={},
            repo_root=_repo_root(),
        )


def test_access_failure_requires_retained_finalizable_provider_status(tmp_path: Path) -> None:
    inventory, _ = _inventory(tmp_path)
    row = next(row for row in inventory.season_rows if row.season_id == "sr:season:access")
    headers = tmp_path / "headers"
    body = tmp_path / "body"
    headers.write_bytes(b"HTTP/1.1 503 Service Unavailable\r\n")
    body.write_bytes(b"temporary outage")

    with pytest.raises(ValueError, match="401/403/404/410"):
        build_provider_access_failure_evidence(
            season=row,
            endpoint_path="seasons/sr:season:access/summaries.json",
            attempted_at=datetime(2026, 9, 14, 19, 10, tzinfo=UTC),
            http_status=503,
            response_headers_path=headers,
            response_body_path=body,
        )


def test_access_failure_cannot_reference_another_endpoint(tmp_path: Path) -> None:
    inventory, _ = _inventory(tmp_path)
    row = next(row for row in inventory.season_rows if row.season_id == "sr:season:access")
    headers = tmp_path / "headers"
    body = tmp_path / "body"
    headers.write_bytes(b"HTTP/1.1 404 Not Found\r\n")
    body.write_bytes(b"not found")

    with pytest.raises(ValueError, match="season's summaries endpoint"):
        build_provider_access_failure_evidence(
            season=row,
            endpoint_path="seasons/sr:season:other/summaries.json",
            attempted_at=datetime(2026, 9, 14, 19, 10, tzinfo=UTC),
            http_status=404,
            response_headers_path=headers,
            response_body_path=body,
        )


def test_tampered_inventory_status_or_count_is_rejected(tmp_path: Path) -> None:
    _, inventory_content = _inventory(tmp_path)
    payload = json.loads(inventory_content)
    payload["historical_candidate_count"] = 999
    tampered = (json.dumps(payload) + "\n").encode()
    with pytest.raises(ValueError, match="historical-candidate count does not reproduce"):
        build_exact_time_panel_manifest(
            inventory_content=tampered,
            admitted_audits={},
            failed_audits={},
            access_failures={},
            repo_root=_repo_root(),
        )
