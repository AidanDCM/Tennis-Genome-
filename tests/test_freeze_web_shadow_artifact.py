from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from scripts import freeze_web_shadow_artifact as freeze


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _build_artifact(tmp_path: Path, *, tamper_prediction: bool = False) -> tuple[Path, str]:
    root = tmp_path / "artifact"
    match_root = root / "web-shadow-slate-run/matches/test-match"
    matchup = {
        "match_id": "web:wta:test:1",
        "player_a_id": "wta:id:100",
        "player_b_id": "wta:id:200",
        "foundational": {"elo_logit": 0.4054651081081644},
    }
    matchup_path = match_root / "matchup-input.json"
    _write_json(matchup_path, matchup)
    matchup_sha = hashlib.sha256(matchup_path.read_bytes()).hexdigest()

    local_manifest = {
        "production_eligible": False,
        "matchup_input_sha256": matchup_sha,
    }
    _write_json(match_root / "local-input-manifest.json", local_manifest)

    prediction = {
        "record_type": "WEB_SHADOW_PREDICTION",
        "schema_version": "tennis-genome-web-shadow-v1",
        "production_eligible": False,
        "model_source_sha": "a" * 40,
        "input_manifest_sha256": matchup_sha,
        "player_a_id": "wta:id:100",
        "player_b_id": "wta:id:200",
        "p_player_a": 0.6,
        "p_player_b": 0.4,
        "selected_player": "Alpha",
        "committed_at": "2026-09-21T10:00:00+00:00",
        "fixture": {
            "match_id": "web:wta:test:1",
            "player_a": "Alpha",
            "player_b": "Beta",
            "scheduled_start": "2026-09-22T10:00:00+00:00",
        },
    }
    prediction["record_sha256"] = freeze._canonical_sha256(prediction)
    if tamper_prediction:
        prediction["p_player_a"] = 0.61
    _write_json(match_root / "prediction.json", prediction)

    manifest = {
        "schema_version": "tennis-genome-web-shadow-slate-v2",
        "production_eligible": False,
        "history_mode": "PINNED_PUBLIC_HISTORY_THROUGH_2026_06_02",
        "eligible_target_count": 1,
        "predicted_target_count": 1,
        "skipped_target_count": 0,
        "results": [
            {
                "artifact_stem": "test-match",
                "match_id": "web:wta:test:1",
                "prediction_path": (
                    "web-shadow-slate-run/matches/test-match/prediction.json"
                ),
                "prediction_record_sha256": prediction["record_sha256"],
                "scheduled_start": "2026-09-22T10:00:00+00:00",
                "selected_player": "Alpha",
                "p_player_a": 0.6,
                "p_player_b": 0.4,
            }
        ],
    }
    _write_json(root / "web-shadow-slate-run/slate-manifest.json", manifest)
    _write_json(
        root / "data/wta-live-base/2026-source-reconciliation.json",
        {"schema_version": "test-reconciliation"},
    )
    _write_json(
        root / "data/wta-live-base/history-cache-receipt.json",
        {"schema_version": "test-cache"},
    )

    archive = tmp_path / "artifact.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                handle.write(path, path.relative_to(root).as_posix())
    return archive, hashlib.sha256(archive.read_bytes()).hexdigest()


def _write_scorecard(repo_root: Path) -> Path:
    scorecard = repo_root / "web-shadow/scorecard.json"
    _write_json(
        scorecard,
        {
            "schema_version": "tennis-genome-web-shadow-scorecard-v1",
            "production_eligible": False,
            "official_slate_count": 0,
            "pending_match_count": 0,
            "settled_match_count": 0,
            "baseline_match_count": 0,
            "slates": [],
        },
    )
    return scorecard


def test_freeze_artifact_builds_official_slate_and_baseline(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    scorecard = _write_scorecard(repo_root)
    archive, digest = _build_artifact(tmp_path)

    summary = freeze.freeze_web_shadow_artifact(
        artifact_zip=archive,
        repo_root=repo_root,
        scorecard_path=Path("web-shadow/scorecard.json"),
        slate_id="2026-09-21-run-123",
        workflow_run_id=123,
        artifact_id=456,
        artifact_sha256=digest,
        workflow_source_sha="a" * 40,
    )

    frozen_root = repo_root / "web-shadow/slates/2026-09-21-run-123"
    assert summary["official_slate_count"] == 1
    assert summary["pending_match_count"] == 1
    assert summary["baseline_match_count"] == 1
    assert (frozen_root / "predictions/test-match.json").is_file()
    assert (frozen_root / "baselines/test-match.json").is_file()
    assert (frozen_root / "slate-receipt.json").is_file()

    baseline = json.loads(
        (frozen_root / "baselines/test-match.json").read_text(encoding="utf-8")
    )
    assert baseline["p_player_a"] == pytest.approx(0.6)
    assert baseline["p_player_b"] == pytest.approx(0.4)
    assert baseline["selected_player"] == "Alpha"
    assert baseline["artifact_id"] == 456
    assert baseline["artifact_sha256"] == digest

    updated = json.loads(scorecard.read_text(encoding="utf-8"))
    assert updated["official_slate_count"] == 1
    assert updated["pending_match_count"] == 1
    assert updated["settled_match_count"] == 0
    assert updated["baseline_match_count"] == 1
    entry = updated["slates"][0]["predictions"][0]
    assert entry["status"] == "PENDING"
    assert entry["selected_probability"] == pytest.approx(0.6)
    assert entry["baseline_path"].endswith("/baselines/test-match.json")


def test_freeze_artifact_rejects_zip_digest_drift(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write_scorecard(repo_root)
    archive, _ = _build_artifact(tmp_path)

    with pytest.raises(ValueError, match="artifact ZIP SHA-256 differs"):
        freeze.freeze_web_shadow_artifact(
            artifact_zip=archive,
            repo_root=repo_root,
            scorecard_path=Path("web-shadow/scorecard.json"),
            slate_id="test-run",
            workflow_run_id=123,
            artifact_id=456,
            artifact_sha256="0" * 64,
            workflow_source_sha="a" * 40,
        )

    assert not (repo_root / "web-shadow/slates/test-run").exists()


def test_freeze_artifact_rejects_prediction_record_tampering(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    scorecard = _write_scorecard(repo_root)
    archive, digest = _build_artifact(tmp_path, tamper_prediction=True)
    original_scorecard = scorecard.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="prediction record digest mismatch"):
        freeze.freeze_web_shadow_artifact(
            artifact_zip=archive,
            repo_root=repo_root,
            scorecard_path=Path("web-shadow/scorecard.json"),
            slate_id="test-run",
            workflow_run_id=123,
            artifact_id=456,
            artifact_sha256=digest,
            workflow_source_sha="a" * 40,
        )

    assert scorecard.read_text(encoding="utf-8") == original_scorecard
    assert not (repo_root / "web-shadow/slates/test-run").exists()


def test_freeze_artifact_rejects_duplicate_slate(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    scorecard = _write_scorecard(repo_root)
    payload = json.loads(scorecard.read_text(encoding="utf-8"))
    payload["slates"] = [{"slate_id": "test-run"}]
    _write_json(scorecard, payload)
    archive, digest = _build_artifact(tmp_path)

    with pytest.raises(ValueError, match="already contains slate"):
        freeze.freeze_web_shadow_artifact(
            artifact_zip=archive,
            repo_root=repo_root,
            scorecard_path=Path("web-shadow/scorecard.json"),
            slate_id="test-run",
            workflow_run_id=123,
            artifact_id=456,
            artifact_sha256=digest,
            workflow_source_sha="a" * 40,
        )


def test_freeze_artifact_rejects_unsafe_zip_paths(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write_scorecard(repo_root)
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../escape.txt", "nope")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()

    with pytest.raises(ValueError, match="unsafe path"):
        freeze.freeze_web_shadow_artifact(
            artifact_zip=archive,
            repo_root=repo_root,
            scorecard_path=Path("web-shadow/scorecard.json"),
            slate_id="test-run",
            workflow_run_id=123,
            artifact_id=456,
            artifact_sha256=digest,
            workflow_source_sha="a" * 40,
        )


def test_freeze_artifact_rolls_back_when_final_scorecard_validation_fails(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    scorecard = _write_scorecard(repo_root)
    payload = json.loads(scorecard.read_text(encoding="utf-8"))
    payload["metrics"] = {}
    _write_json(scorecard, payload)
    original_scorecard = scorecard.read_bytes()
    archive, digest = _build_artifact(tmp_path)

    with pytest.raises(
        ValueError,
        match="scorecard cannot publish metrics without completed settlements",
    ):
        freeze.freeze_web_shadow_artifact(
            artifact_zip=archive,
            repo_root=repo_root,
            scorecard_path=Path("web-shadow/scorecard.json"),
            slate_id="test-run",
            workflow_run_id=123,
            artifact_id=456,
            artifact_sha256=digest,
            workflow_source_sha="a" * 40,
        )

    assert scorecard.read_bytes() == original_scorecard
    assert not (repo_root / "web-shadow/slates/test-run").exists()
