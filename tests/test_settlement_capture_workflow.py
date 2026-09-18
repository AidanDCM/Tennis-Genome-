from __future__ import annotations

from pathlib import Path


def test_settlement_capture_workflow_is_restricted_and_header_authenticated() -> None:
    text = Path(".github/workflows/prospective_settlement_capture.yml").read_text()
    dispatch = text.split("permissions:", maxsplit=1)[0]

    assert "prediction_record_sha256:" in dispatch
    assert "prediction_artifact_id:" in dispatch
    assert "provider_artifact_id:" in dispatch
    assert "prediction_anchor_comment_id:" in dispatch
    assert "identity_binding_sha256:" in dispatch
    assert "sportradar_event_id:" in dispatch
    assert "sportradar_access_level:" in dispatch
    assert "observed_at:" not in dispatch
    assert "winner_sportradar_id:" not in dispatch
    assert "provider_status:" not in dispatch
    assert "timeline_sha256:" not in dispatch
    assert "workflow_source_sha:" not in dispatch
    assert "comment_id:" not in dispatch

    assert "SPORTRADAR_API_KEY: ${{ secrets.SPORTRADAR_API_KEY }}" in text
    assert '"x-api-key": key' in text
    assert "api_key=" not in text.lower()
    assert "python -S -" in text
    assert "pip install" not in text
    assert "actions/checkout@" not in text
    assert "issues: write" in text
    assert "contents: read" in text
    assert "actions: write" in text
    assert "GITHUB_REF_NAME" in text
    assert '!= "main"' in text
    assert "/issues/122/comments" in text
    assert "github-actions[bot]" in text
    assert "generated_at must be timezone-aware" in text


def test_settlement_capture_artifact_action_is_pinned() -> None:
    text = Path(".github/workflows/prospective_settlement_capture.yml").read_text()
    assert (
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"
        in text
    )
    assert "retention-days: 90" in text
    assert (
        "prospective-trusted-settlement-capture-"
        "${{ inputs.prediction_record_sha256 }}"
        in text
    )
    assert "prospective_settlement_finalize.yml/dispatches" in text
    assert "Refuse duplicate" in text
    assert "sportradar_timeline.json" in text
    assert "sportradar_response_headers.json" in text
    assert "trusted_settlement_receipt.json" in text
    assert "github_comment_response.json" in text
