from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tennis_genome.research_workbench.sportradar_exact_time_panel_evidence import (
    EvidenceBoundExactTimePanelReceipt,
    build_evidence_bound_exact_time_panel_receipt,
)
from tennis_genome.research_workbench.sportradar_season_inventory import (
    build_sportradar_season_inventory,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _competition() -> dict[str, object]:
    return {
        "id": "sr:competition:1",
        "name": "ATP Evidence Test",
        "type": "singles",
        "level": "atp_250",
        "category": {"id": "sr:category:3", "name": "ATP"},
    }


def _season(*, name: str = "ATP Evidence Test 2026") -> dict[str, object]:
    return {
        "id": "sr:season:1",
        "name": name,
        "competition_id": "sr:competition:1",
        "start_date": "2026-09-20",
        "end_date": "2026-09-27",
        "year": "2026",
        "disabled": False,
    }


def _raw_evidence(tmp_path: Path) -> tuple[Path, Path, Path]:
    atp = _write_json(
        tmp_path / "atp.json",
        {
            "generated_at": "2026-09-14T19:00:00Z",
            "competitions": [_competition()],
        },
    )
    wta = _write_json(
        tmp_path / "wta.json",
        {"generated_at": "2026-09-14T19:00:30Z", "competitions": []},
    )
    seasons = _write_json(
        tmp_path / "seasons.json",
        {"generated_at": "2026-09-14T19:01:00Z", "seasons": [_season()]},
    )
    return atp, wta, seasons


def _inventory_content(
    *,
    atp: Path,
    wta: Path,
    seasons: Path,
) -> bytes:
    inventory = build_sportradar_season_inventory(
        atp_competitions_path=atp,
        wta_competitions_path=wta,
        season_response_paths={"sr:competition:1": seasons},
        snapshot_at=datetime(2026, 9, 14, 19, 5, tzinfo=UTC),
    )
    return (json.dumps(inventory.canonical_payload(), sort_keys=True) + "\n").encode()


def _receipt(tmp_path: Path) -> EvidenceBoundExactTimePanelReceipt:
    atp, wta, seasons = _raw_evidence(tmp_path)
    inventory_content = _inventory_content(atp=atp, wta=wta, seasons=seasons)
    return build_evidence_bound_exact_time_panel_receipt(
        inventory_content=inventory_content,
        atp_competitions_path=atp,
        wta_competitions_path=wta,
        season_response_paths={"sr:competition:1": seasons},
        admitted_audits={},
        failed_audits={},
        access_failures={},
        repo_root=_repo_root(),
    )


def test_evidence_bound_panel_receipt_rederives_inventory_from_raw_bytes(
    tmp_path: Path,
) -> None:
    receipt = _receipt(tmp_path)

    assert receipt.panel_manifest.not_yet_historical_count == 1
    assert receipt.panel_manifest.historical_candidate_count == 0
    assert receipt.inventory_semantic_sha256 == (
        receipt.panel_manifest.inventory_semantic_sha256
    )
    assert receipt.frozen_inventory.semantic_sha256 == receipt.inventory_semantic_sha256
    assert len(receipt.raw_inventory_evidence) == 3
    assert receipt.raw_inventory_evidence[-1].binding_id == "sr:competition:1"


def test_reloaded_receipt_rejects_raw_evidence_identity_detached_from_inventory(
    tmp_path: Path,
) -> None:
    receipt = _receipt(tmp_path)
    payload = receipt.canonical_payload()
    raw_evidence = payload["raw_inventory_evidence"]
    assert isinstance(raw_evidence, list)
    raw_evidence[-1]["sha256"] = "0" * 64
    payload["raw_inventory_evidence_set_sha256"] = hashlib.sha256(
        json.dumps(
            raw_evidence,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()

    with pytest.raises(ValueError, match="do not match frozen inventory"):
        EvidenceBoundExactTimePanelReceipt.model_validate(payload)


def test_internally_valid_denominator_deleted_inventory_is_rejected(
    tmp_path: Path,
) -> None:
    atp, wta, seasons = _raw_evidence(tmp_path)

    empty_atp = _write_json(
        tmp_path / "empty-atp.json",
        {"generated_at": "2026-09-14T19:00:00Z", "competitions": []},
    )
    empty_wta = _write_json(
        tmp_path / "empty-wta.json",
        {"generated_at": "2026-09-14T19:00:30Z", "competitions": []},
    )
    deleted_inventory = build_sportradar_season_inventory(
        atp_competitions_path=empty_atp,
        wta_competitions_path=empty_wta,
        season_response_paths={},
        snapshot_at=datetime(2026, 9, 14, 19, 5, tzinfo=UTC),
    )
    deleted_content = (
        json.dumps(deleted_inventory.canonical_payload(), sort_keys=True) + "\n"
    ).encode()

    with pytest.raises(ValueError, match="does not exactly re-derive"):
        build_evidence_bound_exact_time_panel_receipt(
            inventory_content=deleted_content,
            atp_competitions_path=atp,
            wta_competitions_path=wta,
            season_response_paths={"sr:competition:1": seasons},
            admitted_audits={},
            failed_audits={},
            access_failures={},
            repo_root=_repo_root(),
        )


def test_raw_competition_seasons_drift_after_inventory_freeze_is_rejected(
    tmp_path: Path,
) -> None:
    atp, wta, seasons = _raw_evidence(tmp_path)
    inventory_content = _inventory_content(atp=atp, wta=wta, seasons=seasons)
    _write_json(
        seasons,
        {
            "generated_at": "2026-09-14T19:01:00Z",
            "seasons": [_season(name="Tampered Season Name")],
        },
    )

    with pytest.raises(ValueError, match="does not exactly re-derive"):
        build_evidence_bound_exact_time_panel_receipt(
            inventory_content=inventory_content,
            atp_competitions_path=atp,
            wta_competitions_path=wta,
            season_response_paths={"sr:competition:1": seasons},
            admitted_audits={},
            failed_audits={},
            access_failures={},
            repo_root=_repo_root(),
        )


def test_missing_required_competition_seasons_evidence_fails_closed(
    tmp_path: Path,
) -> None:
    atp, wta, seasons = _raw_evidence(tmp_path)
    inventory_content = _inventory_content(atp=atp, wta=wta, seasons=seasons)

    with pytest.raises(ValueError, match="evidence set mismatch"):
        build_evidence_bound_exact_time_panel_receipt(
            inventory_content=inventory_content,
            atp_competitions_path=atp,
            wta_competitions_path=wta,
            season_response_paths={},
            admitted_audits={},
            failed_audits={},
            access_failures={},
            repo_root=_repo_root(),
        )
