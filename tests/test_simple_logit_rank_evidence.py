from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from scripts.build_simple_logit_rank_evidence import build_evidence


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(root: Path, raw_name: str, raw: dict, manifest: dict) -> None:
    _write(root / raw_name, raw)
    manifest.update(
        {"raw_wta_sha256" if "standings" in raw_name else "raw_sha256": _hash(root / raw_name)}
    )
    _write(root / "manifest.json", manifest)
    _write(
        root / "github-receipt.json",
        {
            "repository": "AidanDCM/Tennis-Genome-",
            "manifest_sha256": _hash(root / "manifest.json"),
            "workflow_run_id": 11,
        },
    )


def test_retained_rank_evidence_binds_identity_and_source_hashes(tmp_path: Path) -> None:
    event_date = date(2026, 11, 8)
    state = {
        "tour": "WTA",
        "match_id": "match",
        "event_date": event_date.isoformat(),
        "player_a_id": "a",
        "player_b_id": "b",
        "player_a_name": "Claire Liu",
        "player_b_name": "Alexandra Eala",
        "age_years_a": (event_date - date(2000, 5, 25)).days / 365.2425,
        "age_years_b": (event_date - date(2005, 5, 23)).days / 365.2425,
    }
    fixture = {
        "tour": "WTA",
        "match_id": "match",
        "scheduled_start": "2026-11-08T16:00:00+08:00",
    }
    _write(tmp_path / "state.json", state)
    _write(tmp_path / "fixture.json", fixture)
    standings_root, profile_root = tmp_path / "standings", tmp_path / "profiles"
    _source(
        standings_root,
        "raw-wta-standings.json",
        {
            "success": 1,
            "result": [
                {
                    "player_key": 509,
                    "player": "Claire Liu",
                    "league": "WTA",
                    "place": 109,
                    "points": "691",
                },
                {
                    "player_key": 3490,
                    "player": "Alexandra Eala",
                    "league": "WTA",
                    "place": 19,
                    "points": "2241",
                },
            ],
        },
        {"observed_at_utc": "2026-11-02T19:51:38+00:00"},
    )
    _source(
        profile_root,
        "raw-response.json",
        {
            "success": 1,
            "result": [
                {
                    "player_key": 509,
                    "player_full_name": "Claire Liu",
                    "player_bday": "25.05.2000",
                    "player_country": "USA",
                },
                {
                    "player_key": 3490,
                    "player_full_name": "Alexandra Eala",
                    "player_bday": "23.05.2005",
                    "player_country": "Philippines",
                },
            ],
        },
        {"method": "get_players", "received_at_utc": "2026-11-02T19:53:44+00:00"},
    )
    kwargs = dict(
        target_state_path=tmp_path / "state.json",
        fixture_path=tmp_path / "fixture.json",
        standings_root=standings_root,
        profile_root=profile_root,
        standings_artifact_id=12,
        profile_artifact_id=13,
        output_path=tmp_path / "evidence.json",
    )
    result = build_evidence(**kwargs)
    assert [row["rank"] for row in result["players"]] == [109, 19]
    assert result["production_eligible"] is False
    assert build_evidence(**kwargs) == result
    with (standings_root / "raw-wta-standings.json").open("a", encoding="utf-8") as handle:
        handle.write(" ")
    with pytest.raises(ValueError, match="raw hash mismatch"):
        build_evidence(**kwargs)
