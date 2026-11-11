"""Read-only integration regression for the proposed Chennai WTA Web Shadow result.

Runs against the isolated acquisition proposal branch; does not publish evidence.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.settle_web_shadow_result_batch import settle_web_shadow_result_batch


def test_chennai_proposed_batch_dry_run_preserves_scorecard(tmp_path: Path) -> None:
    scorecard = Path("web-shadow/scorecard.json")
    manifest = Path("web-shadow/active-results.json")
    original_scorecard = scorecard.read_bytes()
    original_manifest = manifest.read_bytes()

    summary = settle_web_shadow_result_batch(
        manifest_path=manifest,
        scorecard_path=scorecard,
        output_root=tmp_path / "chennai-dry-run",
    )

    assert summary["production_eligible"] is False
    assert summary["requested_result_count"] == 1
    assert summary["settlement_count"] == 1
    assert summary["evaluation_eligible_count"] == 1
    assert summary["excluded_noncompleted_count"] == 0
    assert summary["correct_prediction_count"] == 1
    assert summary["slate_count"] == 1
    row = summary["results"][0]
    assert row["match_id"] == "web:wta:1148:2026:LS001"
    assert row["winner"] == "Magda Linette"
    assert row["prediction_correct"] is True
    assert row["evaluation_eligible"] is True
    assert len(row["result_record_sha256"]) == 64
    assert len(row["settlement_record_sha256"]) == 64
    settlement = json.loads(Path(row["settlement_output_path"]).read_text())
    assert settlement["production_eligible"] is False
    assert settlement["match_id"] == row["match_id"]
    assert scorecard.read_bytes() == original_scorecard
    assert manifest.read_bytes() == original_manifest
