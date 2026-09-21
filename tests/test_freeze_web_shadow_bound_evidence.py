from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from scripts import freeze_web_shadow_bound_evidence as freeze


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _record(payload: dict[str, object]) -> dict[str, object]:
    payload["record_sha256"] = freeze._canonical_sha256(payload)
    return payload


def _build_bound_artifact(tmp_path: Path, *, tamper_baseline: bool = False) -> tuple[Path, str]:
    root = tmp_path / "bound"
    source_sha = "a" * 40
    raw_digest = "b" * 64
    match_id = "web:wta:test:1"
    stem = "test-match"

    prediction = _record(
        {
            "record_type": "WEB_SHADOW_PREDICTION",
            "schema_version": "tennis-genome-web-shadow-v1",
            "production_eligible": False,
            "model_source_sha": source_sha,
            "p_player_a": 0.6,
            "p_player_b": 0.4,
            "selected_player": "Alpha",
            "fixture": {
                "match_id": match_id,
                "player_a": "Alpha",
                "player_b": "Beta",
                "scheduled_start": "2026-09-23T10:00:00+00:00",
            },
        }
    )
    candidate = _record(
        {
            "schema_version": "tennis-genome-web-shadow-baseline-candidate-v1",
            "record_type": "WEB_SHADOW_BASELINE_CANDIDATE",
            "baseline_name": "overall_elo_v1",
            "match_id": match_id,
            "prediction_record_sha256": prediction["record_sha256"],
            "matchup_input_sha256": "c" * 64,
            "elo_logit": 0.4054651081081644,
            "p_player_a": 0.6,
            "p_player_b": 0.4,
            "selected_player": "Alpha",
            "production_eligible": False,
        }
    )
    baseline = _record(
        {
            "schema_version": "tennis-genome-web-shadow-baseline-v1",
            "record_type": "WEB_SHADOW_ELO_BASELINE",
            "baseline_name": "overall_elo_v1",
            "slate_id": "2026-09-21-run-123",
            "match_id": match_id,
            "prediction_record_sha256": prediction["record_sha256"],
            "matchup_input_sha256": "c" * 64,
            "elo_logit": 0.4054651081081644,
            "p_player_a": 0.6,
            "p_player_b": 0.4,
            "selected_player": "Alpha",
            "artifact_id": 456,
            "artifact_sha256": raw_digest,
            "production_eligible": False,
        }
    )
    if tamper_baseline:
        baseline["p_player_a"] = 0.7

    _write_json(root / f"predictions/{stem}.json", prediction)
    _write_json(root / f"baseline-candidates/{stem}.json", candidate)
    _write_json(root / f"baselines/{stem}.json", baseline)
    receipt = {
        "schema_version": "tennis-genome-web-shadow-slate-receipt-v1",
        "slate_id": "2026-09-21-run-123",
        "workflow_run_id": 123,
        "workflow_artifact_id": 456,
        "workflow_artifact_sha256": raw_digest,
        "workflow_source_sha": source_sha,
        "history_mode": "PINNED_PUBLIC_HISTORY_THROUGH_2026_06_02",
        "eligible_target_count": 1,
        "predicted_target_count": 1,
        "skipped_target_count": 0,
        "production_eligible": False,
        "scorecard_eligible": True,
    }
    manifest = {
        "schema_version": "tennis-genome-web-shadow-bound-evidence-v1",
        "slate_id": "2026-09-21-run-123",
        "production_eligible": False,
        "workflow_run_id": 123,
        "workflow_artifact_id": 456,
        "workflow_artifact_sha256": raw_digest,
        "workflow_source_sha": source_sha,
        "eligible_target_count": 1,
        "predicted_target_count": 1,
        "skipped_target_count": 0,
        "baseline_count": 1,
        "results": [
            {
                "artifact_stem": stem,
                "match_id": match_id,
                "prediction_path": f"predictions/{stem}.json",
                "prediction_record_sha256": prediction["record_sha256"],
                "baseline_candidate_path": f"baseline-candidates/{stem}.json",
                "baseline_candidate_record_sha256": candidate["record_sha256"],
                "baseline_path": f"baselines/{stem}.json",
                "baseline_record_sha256": baseline["record_sha256"],
            }
        ],
    }
    _write_json(root / "bound-evidence-manifest.json", manifest)
    _write_json(root / "slate-receipt.json", receipt)
    _write_json(
        root / "slate-manifest.json",
        {
            "schema_version": "tennis-genome-web-shadow-slate-v2",
            "production_eligible": False,
            "history_mode": receipt["history_mode"],
        },
    )
    _write_json(root / "source-reconciliation.json", {"schema_version": "test"})
    _write_json(root / "history-cache-receipt.json", {"schema_version": "test"})

    archive = tmp_path / "bound.zip"
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


def test_freeze_bound_evidence_uses_finalized_records_without_rederiving(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    scorecard = _write_scorecard(repo_root)
    archive, digest = _build_bound_artifact(tmp_path)

    summary = freeze.freeze_web_shadow_bound_evidence(
        artifact_zip=archive,
        repo_root=repo_root,
        scorecard_path=Path("web-shadow/scorecard.json"),
        bound_artifact_id=789,
        bound_artifact_sha256=digest,
    )

    frozen = repo_root / "web-shadow/slates/2026-09-21-run-123"
    assert summary["raw_artifact_id"] == 456
    assert summary["bound_artifact_id"] == 789
    assert summary["pending_match_count"] == 1
    assert (frozen / "predictions/test-match.json").is_file()
    assert (frozen / "baselines/test-match.json").is_file()
    assert (frozen / "baseline-candidates/test-match.json").is_file()
    assert (frozen / "bound-evidence-manifest.json").is_file()
    assert (frozen / "bound-artifact-receipt.json").is_file()

    updated = json.loads(scorecard.read_text(encoding="utf-8"))
    assert updated["official_slate_count"] == 1
    assert updated["baseline_match_count"] == 1
    assert updated["slates"][0]["predictions"][0]["selected_probability"] == pytest.approx(0.6)


def test_freeze_bound_evidence_rejects_tampered_baseline(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    scorecard = _write_scorecard(repo_root)
    original = scorecard.read_bytes()
    archive, digest = _build_bound_artifact(tmp_path, tamper_baseline=True)

    with pytest.raises(ValueError, match="baseline record digest mismatch"):
        freeze.freeze_web_shadow_bound_evidence(
            artifact_zip=archive,
            repo_root=repo_root,
            scorecard_path=Path("web-shadow/scorecard.json"),
            bound_artifact_id=789,
            bound_artifact_sha256=digest,
        )

    assert scorecard.read_bytes() == original
    assert not (repo_root / "web-shadow/slates/2026-09-21-run-123").exists()


def test_freeze_bound_evidence_rejects_outer_digest_drift(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _write_scorecard(repo_root)
    archive, _ = _build_bound_artifact(tmp_path)

    with pytest.raises(ValueError, match="bound artifact ZIP SHA-256 differs"):
        freeze.freeze_web_shadow_bound_evidence(
            artifact_zip=archive,
            repo_root=repo_root,
            scorecard_path=Path("web-shadow/scorecard.json"),
            bound_artifact_id=789,
            bound_artifact_sha256="0" * 64,
        )
