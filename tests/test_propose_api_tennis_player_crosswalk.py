from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from scripts.propose_api_tennis_player_crosswalk import propose
from tennis_genome.independent.production import PINNED_SOURCE_COMMIT


def _write_json(path: Path, value: object) -> bytes:
    raw = json.dumps(value, sort_keys=True).encode("utf-8")
    path.write_bytes(raw)
    return raw


def _inputs(
    root: Path, *, draw_identity: bool = True, second_birthdate: str = "04.03.2000"
) -> tuple[Path, Path, Path]:
    archive = root / "archive.zip"
    with zipfile.ZipFile(archive, "w") as source:
        prefix = f"tennis-sackmann-archive-{PINNED_SOURCE_COMMIT}"
        source.writestr(f"{prefix}/atp/atp_players.csv", "")
        source.writestr(
            f"{prefix}/wta/wta_players.csv",
            "101,Ada,Example,R,19990102,USA,170\n102,Bella,Sample,L,20000304,USA,175\n",
        )
    retained = root / "retained"
    name = "api-tennis-metadata-get_players-77-2026"
    directory = retained / name / name
    directory.mkdir(parents=True)
    raw = _write_json(
        directory / "raw-response.json",
        {
            "success": 1,
            "result": [
                {
                    "player_key": 11,
                    "player_full_name": "Ada Example",
                    "player_bday": "02.01.1999",
                },
                {
                    "player_key": 22,
                    "player_full_name": "Bella Sample",
                    "player_bday": second_birthdate,
                },
            ],
        },
    )
    manifest = _write_json(
        directory / "manifest.json",
        {"method": "get_players", "raw_sha256": hashlib.sha256(raw).hexdigest()},
    )
    _write_json(
        directory / "github-receipt.json",
        {"manifest_sha256": hashlib.sha256(manifest).hexdigest(), "workflow_run_id": 123},
    )
    slate = root / "slate.json"
    _write_json(
        slate,
        {
            "schema_version": "tennis-genome-offline-slate-field-audit-v1",
            "schedule_date": "2026-11-03",
            "fixture_count": 1,
            "matches": [
                {
                    "event_key": 777,
                    "tour": "WTA",
                    "tournament_key": 77,
                    "fixture_player_keys": [11, 22],
                    "fixture_status_at_capture": "1",
                    "fields": {"draw_identity": draw_identity},
                }
            ],
        },
    )
    return archive, retained, slate


def test_exact_name_and_birthdate_propose_both_canonical_ids(tmp_path: Path) -> None:
    archive, retained, slate = _inputs(tmp_path)

    result = propose(archive=archive, retained_root=retained, slate_report=slate)

    assert result["status_counts"] == {"EXACT_CANDIDATE": 1}
    assert result["matches"][0]["canonical_player_ids"] == ["wta:id:101", "wta:id:102"]
    assert result["production_admitted"] is False


def test_fixture_draw_conflict_cannot_propose_identity(tmp_path: Path) -> None:
    archive, retained, slate = _inputs(tmp_path, draw_identity=False)

    result = propose(archive=archive, retained_root=retained, slate_report=slate)

    assert result["status_counts"] == {"FIXTURE_DRAW_ID_CONFLICT": 1}
    assert result["matches"][0]["canonical_player_ids"] is None


def test_birthdate_mismatch_cannot_propose_identity(tmp_path: Path) -> None:
    archive, retained, slate = _inputs(tmp_path, second_birthdate="04.03.2001")

    result = propose(archive=archive, retained_root=retained, slate_report=slate)

    assert result["status_counts"] == {"NO_EXACT_REGISTRY_MATCH": 1}
    assert result["matches"][0]["canonical_player_ids"] is None


def test_tampered_profile_is_rejected(tmp_path: Path) -> None:
    archive, retained, slate = _inputs(tmp_path)
    raw = retained / "api-tennis-metadata-get_players-77-2026"
    raw = raw / raw.name / "raw-response.json"
    raw.write_bytes(raw.read_bytes() + b" ")

    with pytest.raises(ValueError, match="raw response hash mismatch"):
        propose(archive=archive, retained_root=retained, slate_report=slate)
