from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from scripts import apply_web_shadow_settlement_batch as apply
from scripts.validate_web_shadow_scorecard import validate_web_shadow_scorecard
from tennis_genome.prospective.web_shadow import (
    WebShadowFixture,
    WebShadowPrediction,
    settle_web_shadow,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _fixture(
    tmp_path: Path,
    *,
    settlement_status: str = "COMPLETED",
) -> tuple[Path, Path, Path, str]:
    repo_root = tmp_path / "repo"
    slate_id = "test-slate"
    match_id = "web:wta:test:1"
    source_sha = "d" * 40

    prediction_path = (
        repo_root / f"web-shadow/slates/{slate_id}/predictions/test.json"
    )
    prediction_path.parent.mkdir(parents=True, exist_ok=True)
    prediction = WebShadowPrediction(
        fixture=WebShadowFixture(
            match_id=match_id,
            tour="WTA",
            tournament="Test Open",
            round="R32",
            surface="Hard",
            scheduled_start="2026-09-22T12:00:00+00:00",
            player_a="Alpha",
            player_b="Beta",
            source_url="https://example.com/fixture",
            source_observed_at="2026-09-21T09:00:00+00:00",
        ),
        committed_at="2026-09-21T10:00:00+00:00",
        p_player_a=0.7,
        p_player_b=0.3,
        model_source_sha=source_sha,
        input_manifest_sha256="e" * 64,
    ).record()
    _write_json(prediction_path, prediction)

    receipt_path = repo_root / f"web-shadow/slates/{slate_id}/slate-receipt.json"
    _write_json(
        receipt_path,
        {
            "schema_version": "tennis-genome-web-shadow-slate-receipt-v1",
            "slate_id": slate_id,
            "workflow_run_id": 111,
            "workflow_artifact_id": 222,
            "workflow_artifact_sha256": "f" * 64,
            "workflow_source_sha": source_sha,
            "history_mode": "PINNED_PUBLIC_HISTORY_THROUGH_2026_06_02",
            "eligible_target_count": 1,
            "predicted_target_count": 1,
            "skipped_target_count": 0,
            "production_eligible": False,
            "scorecard_eligible": True,
        },
    )

    scorecard_path = repo_root / "web-shadow/scorecard.json"
    _write_json(
        scorecard_path,
        {
            "schema_version": "tennis-genome-web-shadow-scorecard-v1",
            "production_eligible": False,
            "official_slate_count": 1,
            "pending_match_count": 1,
            "settled_match_count": 0,
            "baseline_match_count": 0,
            "slates": [
                {
                    "slate_id": slate_id,
                    "receipt_path": receipt_path.relative_to(repo_root).as_posix(),
                    "workflow_run_id": 111,
                    "history_mode": "PINNED_PUBLIC_HISTORY_THROUGH_2026_06_02",
                    "status": "PENDING_SETTLEMENT",
                    "predictions": [
                        {
                            "match_id": match_id,
                            "prediction_path": prediction_path.relative_to(
                                repo_root
                            ).as_posix(),
                            "prediction_record_sha256": prediction["record_sha256"],
                            "selected_player": "Alpha",
                            "selected_probability": 0.7,
                            "scheduled_start": "2026-09-22T12:00:00+00:00",
                            "status": "PENDING",
                        }
                    ],
                }
            ],
        },
    )

    result_path = repo_root / "web-shadow/results/test.json"
    _write_json(
        result_path,
        {
            "schema_version": "tennis-genome-web-shadow-public-result-v1",
            "match_id": match_id,
            "prediction_path": prediction_path.relative_to(repo_root).as_posix(),
            "expected_prediction_record_sha256": prediction["record_sha256"],
            "winner": "Alpha",
            "status": settlement_status,
            "score": "6-3 6-4",
            "result_source_url": "https://example.com/result",
            "result_observed_at": "2026-09-22T16:00:00+00:00",
            "production_eligible": False,
        },
    )

    settlement = settle_web_shadow(
        prediction,
        winner="Alpha",
        status=settlement_status,
        result_source_url="https://example.com/result",
        result_observed_at="2026-09-22T16:00:00+00:00",
    )
    settlement["result_record_path"] = result_path.relative_to(repo_root).as_posix()
    settlement["production_eligible"] = False
    unsigned = dict(settlement)
    unsigned.pop("record_sha256", None)
    settlement["record_sha256"] = apply._canonical_sha256(unsigned)

    artifact_root = tmp_path / "artifact"
    settlement_output = (
        artifact_root
        / f"web-shadow-settlement-batch/{slate_id}/settlements/test.json"
    )
    _write_json(settlement_output, settlement)

    eligible = settlement_status == "COMPLETED"
    prediction_correct = True
    summary = {
        "schema_version": "tennis-genome-web-shadow-settlement-batch-v1",
        "production_eligible": False,
        "requested_result_count": 1,
        "settlement_count": 1,
        "evaluation_eligible_count": int(eligible),
        "excluded_noncompleted_count": int(not eligible),
        "correct_prediction_count": int(eligible and prediction_correct),
        "accuracy": 1.0 if eligible else None,
        "slate_count": 1,
        "results": [
            {
                "slate_id": slate_id,
                "match_id": match_id,
                "result_path": result_path.relative_to(repo_root).as_posix(),
                "result_record_sha256": apply._sha256_file(result_path),
                "prediction_path": prediction_path.relative_to(repo_root).as_posix(),
                "prediction_record_sha256": prediction["record_sha256"],
                "settlement_output_path": (
                    f"web-shadow-settlement-batch/{slate_id}/settlements/test.json"
                ),
                "settlement_record_sha256": settlement["record_sha256"],
                "winner": "Alpha",
                "prediction_correct": prediction_correct,
                "evaluation_eligible": eligible,
            }
        ],
    }
    _write_json(
        artifact_root / "web-shadow-settlement-batch/settlement-batch-summary.json",
        summary,
    )
    _write_json(
        artifact_root / "web-shadow-settlement-batch/result-batch-manifest.json",
        {
            "schema_version": "tennis-genome-web-shadow-result-batch-v1",
            "result_paths": [result_path.relative_to(repo_root).as_posix()],
        },
    )

    archive = tmp_path / "settlement-batch.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(artifact_root.rglob("*")):
            if path.is_file():
                handle.write(path, path.relative_to(artifact_root).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    return repo_root, scorecard_path, archive, digest


def _apply(
    *,
    repo_root: Path,
    scorecard_path: Path,
    archive: Path,
    digest: str,
) -> dict[str, object]:
    return apply.apply_web_shadow_settlement_batch(
        artifact_zip=archive,
        repo_root=repo_root,
        scorecard_path=scorecard_path,
        source_workflow_run_id=9001,
        source_workflow_sha="d" * 40,
        settlement_artifact_id=7001,
        settlement_artifact_sha256=digest,
    )


def test_apply_settlement_batch_updates_official_book_and_provenance(
    tmp_path: Path,
) -> None:
    repo_root, scorecard_path, archive, digest = _fixture(tmp_path)

    summary = _apply(
        repo_root=repo_root,
        scorecard_path=scorecard_path,
        archive=archive,
        digest=digest,
    )

    scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))
    entry = scorecard["slates"][0]["predictions"][0]
    assert entry["status"] == "SETTLED"
    assert len(entry["settlement_record_sha256"]) == 64
    assert len(entry["result_record_sha256"]) == 64
    assert scorecard["pending_match_count"] == 0
    assert scorecard["settled_match_count"] == 1
    assert scorecard["metrics"]["accuracy"] == pytest.approx(1.0)
    assert scorecard["metrics"]["settled_match_count"] == 1
    assert scorecard["slates"][0]["status"] == "SETTLED"
    assert summary["applied_settlement_count"] == 1
    assert summary["evaluation_eligible_count"] == 1

    settlement = repo_root / entry["settlement_path"]
    assert settlement.is_file()
    receipt_dir = repo_root / "web-shadow/settlement-batches/9001"
    assert (receipt_dir / "settlement-batch-summary.json").is_file()
    assert (receipt_dir / "result-batch-manifest.json").is_file()
    receipt = json.loads(
        (receipt_dir / "artifact-receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["source_workflow_run_id"] == 9001
    assert receipt["source_workflow_sha"] == "d" * 40
    assert receipt["settlement_artifact_id"] == 7001
    assert receipt["settlement_artifact_sha256"] == digest

    validate_web_shadow_scorecard(
        scorecard_path=scorecard_path,
        repo_root=repo_root,
    )


def test_apply_retirement_retains_settlement_but_excludes_metrics(
    tmp_path: Path,
) -> None:
    repo_root, scorecard_path, archive, digest = _fixture(
        tmp_path,
        settlement_status="RETIREMENT",
    )

    summary = _apply(
        repo_root=repo_root,
        scorecard_path=scorecard_path,
        archive=archive,
        digest=digest,
    )

    scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))
    assert scorecard["settled_match_count"] == 1
    assert scorecard["pending_match_count"] == 0
    assert "metrics" not in scorecard
    assert summary["evaluation_eligible_count"] == 0
    assert summary["excluded_noncompleted_count"] == 1


def test_apply_rejects_committed_result_drift_without_mutation(
    tmp_path: Path,
) -> None:
    repo_root, scorecard_path, archive, digest = _fixture(tmp_path)
    original_scorecard = scorecard_path.read_bytes()
    result_path = repo_root / "web-shadow/results/test.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["score"] = "0-6 0-6"
    _write_json(result_path, result)

    with pytest.raises(ValueError, match="committed result file SHA differs"):
        _apply(
            repo_root=repo_root,
            scorecard_path=scorecard_path,
            archive=archive,
            digest=digest,
        )

    assert scorecard_path.read_bytes() == original_scorecard
    assert not (
        repo_root / "web-shadow/slates/test-slate/settlements/test.json"
    ).exists()
    assert not (repo_root / "web-shadow/settlement-batches/9001").exists()


def test_apply_rolls_back_after_final_validation_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repo_root, scorecard_path, archive, digest = _fixture(tmp_path)
    original_scorecard = scorecard_path.read_bytes()

    def _fail_validation(**_: object) -> dict[str, int]:
        raise ValueError("forced final validation failure")

    monkeypatch.setattr(apply, "validate_web_shadow_scorecard", _fail_validation)

    with pytest.raises(ValueError, match="forced final validation failure"):
        _apply(
            repo_root=repo_root,
            scorecard_path=scorecard_path,
            archive=archive,
            digest=digest,
        )

    assert scorecard_path.read_bytes() == original_scorecard
    assert not (
        repo_root / "web-shadow/slates/test-slate/settlements/test.json"
    ).exists()
    assert not (repo_root / "web-shadow/settlement-batches/9001").exists()


def test_apply_rejects_outer_artifact_digest_drift(tmp_path: Path) -> None:
    repo_root, scorecard_path, archive, _ = _fixture(tmp_path)

    with pytest.raises(ValueError, match="settlement artifact ZIP SHA-256 differs"):
        _apply(
            repo_root=repo_root,
            scorecard_path=scorecard_path,
            archive=archive,
            digest="0" * 64,
        )
