from __future__ import annotations

from pathlib import Path


def test_prediction_anchor_workflow_is_self_contained_and_restricted() -> None:
    text = Path(".github/workflows/prospective_evidence_anchor.yml").read_text()

    assert "prediction_record_sha256:" in text
    assert "chain_head_sha256:" in text
    assert "issues: write" in text
    assert "contents: read" in text
    assert "python -S -" in text
    assert "github-actions[bot]" in text
    assert "issues/119/comments" in text
    assert "GITHUB_REF_NAME" in text
    assert '!= "main"' in text
    assert "actions/checkout@" not in text
    assert "actions/upload-artifact@" not in text
    assert "pip install" not in text


def test_prediction_anchor_workflow_does_not_accept_time_or_run_identity_inputs() -> None:
    text = Path(".github/workflows/prospective_evidence_anchor.yml").read_text()
    dispatch = text.split("permissions:", maxsplit=1)[0]

    forbidden = (
        "created_at:",
        "runner_receipt_created_at_utc:",
        "workflow_run_id:",
        "workflow_source_sha:",
        "comment_id:",
    )
    for field in forbidden:
        assert field not in dispatch
