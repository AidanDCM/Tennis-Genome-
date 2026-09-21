from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.derive_web_shadow_elo_baseline import _canonical_sha256
from scripts.finalize_web_shadow_slate_evidence import (
    finalize_web_shadow_slate_evidence,
)


def _write_prediction(path: Path, *, committed_at: str, match_id: str) -> dict[str, object]:
    payload: dict[str, object] = {
        "record_type": "WEB_SHADOW_PREDICTION",
        "schema_version": "tennis-genome-web-shadow-v1",
        "production_eligible": False,
        "committed_at": committed_at,
        "player_a_id": "wta:id:100",
        "player_b_id": "wta:id:200",
        "p_player_a": 0.6,
        "p_player_b": 0.4,
        "selected_player": "Alpha",
        "fixture": {
            "match_id": match_id,
            "player_a": "Alpha",
            "player_b": "Beta",
        },
    }
    payload["record_sha256"] = _canonical_sha256(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def _write_candidate(
    path: Path,
    *,
    prediction_sha: str,
    match_id: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "tennis-genome-web-shadow-baseline-candidate-v1",
        "record_type": "WEB_SHADOW_BASELINE_CANDIDATE",
        "baseline_name": "overall_elo_v1",
        "match_id": match_id,
        "prediction_record_sha256": prediction_sha,
        "matchup_input_sha256": "d" * 64,
        "elo_logit": 0.4054651081081644,
        "p_player_a": 0.6,
        "p_player_b": 0.4,
        "selected_player": "Alpha",
        "production_eligible": False,
    }
    payload["record_sha256"] = _canonical_sha256(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def _artifact(
    root: Path,
    *,
    committed_dates: list[str] | None = None,
) -> tuple[Path, Path, Path]:
    slate_root = root / "web-shadow-slate-run"
    dates = committed_dates or ["2026-09-21T18:00:00+00:00"]
    results = []
    for index, committed_at in enumerate(dates, start=1):
        stem = f"match-{index}"
        match_id = f"web:wta:test:{index}"
        prediction_path = slate_root / "matches" / stem / "prediction.json"
        prediction = _write_prediction(
            prediction_path,
            committed_at=committed_at,
            match_id=match_id,
        )
        candidate_path = slate_root / "matches" / stem / "baseline-candidate.json"
        candidate = _write_candidate(
            candidate_path,
            prediction_sha=str(prediction["record_sha256"]),
            match_id=match_id,
        )
        results.append(
            {
                "artifact_stem": stem,
                "match_id": match_id,
                "prediction_path": prediction_path.relative_to(root).as_posix(),
                "prediction_record_sha256": prediction["record_sha256"],
                "baseline_candidate_path": candidate_path.relative_to(root).as_posix(),
                "baseline_candidate_record_sha256": candidate["record_sha256"],
            }
        )

    manifest = {
        "schema_version": "tennis-genome-web-shadow-slate-v2",
        "production_eligible": False,
        "history_mode": "PINNED_PUBLIC_HISTORY_THROUGH_2026_06_02",
        "eligible_target_count": len(results),
        "predicted_target_count": len(results),
        "skipped_target_count": 0,
        "results": results,
    }
    slate_root.mkdir(parents=True, exist_ok=True)
    (slate_root / "slate-manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    reconciliation = root / "2026-source-reconciliation.json"
    reconciliation.write_text(json.dumps({"schema_version": "recon"}), encoding="utf-8")
    cache = root / "history-cache-receipt.json"
    cache.write_text(json.dumps({"schema_version": "cache"}), encoding="utf-8")
    return slate_root, reconciliation, cache


def test_finalize_bound_evidence_packages_predictions_and_baselines(
    tmp_path: Path,
) -> None:
    slate_root, reconciliation, cache = _artifact(tmp_path)
    output = tmp_path / "bound"

    summary = finalize_web_shadow_slate_evidence(
        slate_root=slate_root,
        source_reconciliation_path=reconciliation,
        history_cache_receipt_path=cache,
        workflow_run_id=12345,
        workflow_artifact_id=67890,
        workflow_artifact_sha256="sha256:" + "b" * 64,
        workflow_source_sha="c" * 40,
        output_root=output,
    )

    assert summary["slate_id"] == "2026-09-21-run-12345"
    assert summary["baseline_count"] == 1
    assert summary["workflow_artifact_sha256"] == "b" * 64
    assert (output / "predictions/match-1.json").is_file()
    assert (output / "baseline-candidates/match-1.json").is_file()
    assert (output / "baselines/match-1.json").is_file()
    assert (output / "slate-receipt.json").is_file()
    assert (output / "slate-manifest.json").is_file()
    assert (output / "source-reconciliation.json").is_file()
    assert (output / "history-cache-receipt.json").is_file()

    baseline = json.loads(
        (output / "baselines/match-1.json").read_text(encoding="utf-8")
    )
    assert baseline["slate_id"] == "2026-09-21-run-12345"
    assert baseline["artifact_id"] == 67890
    assert baseline["artifact_sha256"] == "b" * 64
    assert baseline["p_player_a"] == pytest.approx(0.6)
    assert baseline["selected_player"] == "Alpha"

    receipt = json.loads(
        (output / "slate-receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["workflow_run_id"] == 12345
    assert receipt["workflow_artifact_id"] == 67890
    assert receipt["workflow_artifact_sha256"] == "b" * 64
    assert receipt["scorecard_eligible"] is True


def test_finalize_bound_evidence_rejects_prediction_digest_drift(
    tmp_path: Path,
) -> None:
    slate_root, reconciliation, cache = _artifact(tmp_path)
    prediction_path = slate_root / "matches/match-1/prediction.json"
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    prediction["p_player_a"] = 0.9
    prediction_path.write_text(json.dumps(prediction), encoding="utf-8")

    with pytest.raises(ValueError, match="prediction record digest mismatch"):
        finalize_web_shadow_slate_evidence(
            slate_root=slate_root,
            source_reconciliation_path=reconciliation,
            history_cache_receipt_path=cache,
            workflow_run_id=12345,
            workflow_artifact_id=67890,
            workflow_artifact_sha256="b" * 64,
            workflow_source_sha="c" * 40,
            output_root=tmp_path / "bound",
        )


def test_finalize_bound_evidence_rejects_candidate_digest_drift(
    tmp_path: Path,
) -> None:
    slate_root, reconciliation, cache = _artifact(tmp_path)
    candidate_path = slate_root / "matches/match-1/baseline-candidate.json"
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate["p_player_a"] = 0.9
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    with pytest.raises(ValueError, match="candidate record digest mismatch"):
        finalize_web_shadow_slate_evidence(
            slate_root=slate_root,
            source_reconciliation_path=reconciliation,
            history_cache_receipt_path=cache,
            workflow_run_id=12345,
            workflow_artifact_id=67890,
            workflow_artifact_sha256="b" * 64,
            workflow_source_sha="c" * 40,
            output_root=tmp_path / "bound",
        )


def test_finalize_bound_evidence_rejects_mixed_commitment_dates(
    tmp_path: Path,
) -> None:
    slate_root, reconciliation, cache = _artifact(
        tmp_path,
        committed_dates=[
            "2026-09-21T23:59:00+00:00",
            "2026-09-22T00:01:00+00:00",
        ],
    )

    with pytest.raises(ValueError, match="share one UTC commitment date"):
        finalize_web_shadow_slate_evidence(
            slate_root=slate_root,
            source_reconciliation_path=reconciliation,
            history_cache_receipt_path=cache,
            workflow_run_id=12345,
            workflow_artifact_id=67890,
            workflow_artifact_sha256="b" * 64,
            workflow_source_sha="c" * 40,
            output_root=tmp_path / "bound",
        )
