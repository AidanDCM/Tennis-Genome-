from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tennis_genome.prospective.provider_batch_github_anchor import (
    ANCHOR_BOT_LOGIN,
    ANCHOR_LEDGER_ISSUE,
    ANCHOR_RECEIPT_SCHEMA,
    ANCHOR_REPOSITORY,
    ANCHOR_WORKFLOW_PATH,
    build_anchor_comment_body,
    fetch_trusted_capture_anchor_evidence,
)
from tennis_genome.prospective.provider_batch_pagination import PAGINATION_SCHEMA
from tennis_genome.prospective.trusted_provider_capture import (
    TRUSTED_CAPTURE_SCHEMA,
    TRUSTED_CAPTURE_WORKFLOW_PATH,
)

_COMMENT_ID = 22334455
_RUN_ID = 66778899
_SOURCE_SHA = "d" * 40


def _batch() -> dict[str, object]:
    return {
        "record_type": "PROVIDER_BATCH",
        "provider": "SPORTRADAR",
        "pagination_schema": PAGINATION_SCHEMA,
        "record_sha256": "a" * 64,
        "schedule_date": "2026-09-15",
        "observed_at": "2026-09-15T12:00:00+00:00",
        "provider_generated_at_min": "2026-09-15T11:55:00+00:00",
        "provider_generated_at_max": "2026-09-15T11:58:00+00:00",
        "raw_payload_sha256": "b" * 64,
        "manifest_sha256": "c" * 64,
    }


def _receipt(*, trusted: bool = True) -> dict[str, object]:
    batch = _batch()
    receipt: dict[str, object] = {
        "schema_version": ANCHOR_RECEIPT_SCHEMA,
        "provider": "GITHUB_ACTIONS",
        "repository": ANCHOR_REPOSITORY,
        "workflow_source_sha": _SOURCE_SHA,
        "workflow_run_id": _RUN_ID,
        "workflow_run_attempt": 1,
        "workflow_run_url": f"https://github.com/{ANCHOR_REPOSITORY}/actions/runs/{_RUN_ID}",
        "batch_record_sha256": batch["record_sha256"],
        "batch_chain_head_sha256": batch["record_sha256"],
        "schedule_date": batch["schedule_date"],
        "raw_payload_sha256": batch["raw_payload_sha256"],
        "manifest_sha256": batch["manifest_sha256"],
        "observed_at": batch["observed_at"],
        "runner_receipt_created_at_utc": "2026-09-15T12:03:00+00:00",
    }
    if trusted:
        receipt.update(
            {
                "trusted_capture_schema": TRUSTED_CAPTURE_SCHEMA,
                "trusted_capture_receipt_sha256": "e" * 64,
                "sportradar_access_level": "production",
            }
        )
    return receipt


def _comment(receipt: dict[str, object]) -> dict[str, object]:
    created = "2026-09-15T12:05:00+00:00"
    return {
        "id": _COMMENT_ID,
        "url": (
            f"https://api.github.com/repos/{ANCHOR_REPOSITORY}/issues/comments/{_COMMENT_ID}"
        ),
        "issue_url": (
            f"https://api.github.com/repos/{ANCHOR_REPOSITORY}/issues/{ANCHOR_LEDGER_ISSUE}"
        ),
        "body": build_anchor_comment_body(receipt),
        "user": {"login": ANCHOR_BOT_LOGIN, "type": "Bot"},
        "created_at": created,
        "updated_at": created,
    }


def _run(
    *,
    path: str = TRUSTED_CAPTURE_WORKFLOW_PATH,
    head_branch: str = "main",
) -> dict[str, object]:
    return {
        "id": _RUN_ID,
        "run_attempt": 1,
        "event": "workflow_dispatch",
        "status": "completed",
        "conclusion": "success",
        "path": path,
        "head_branch": head_branch,
        "head_sha": _SOURCE_SHA,
        "html_url": f"https://github.com/{ANCHOR_REPOSITORY}/actions/runs/{_RUN_ID}",
        "created_at": "2026-09-15T12:02:00+00:00",
        "repository": {"full_name": ANCHOR_REPOSITORY},
    }


def _transport(
    receipt: dict[str, object],
    run: dict[str, object],
) -> Callable[[str], bytes]:
    comment_bytes = json.dumps(_comment(receipt), sort_keys=True).encode("utf-8")
    run_bytes = json.dumps(run, sort_keys=True).encode("utf-8")
    comment_url = (
        f"https://api.github.com/repos/{ANCHOR_REPOSITORY}/issues/comments/{_COMMENT_ID}"
    )
    run_url = f"https://api.github.com/repos/{ANCHOR_REPOSITORY}/actions/runs/{_RUN_ID}"

    def get_bytes(url: str) -> bytes:
        if url == comment_url:
            return comment_bytes
        if url == run_url:
            return run_bytes
        raise AssertionError(f"unexpected GitHub API URL: {url}")

    return get_bytes


def test_trusted_capture_live_verifier_requires_trusted_workflow_and_main() -> None:
    evidence = fetch_trusted_capture_anchor_evidence(
        comment_id=_COMMENT_ID,
        batch_record=_batch(),
        get_bytes=_transport(_receipt(), _run()),
    )
    assert evidence.anchor_created_at == datetime(2026, 9, 15, 12, 5, tzinfo=UTC)
    assert evidence.receipt["trusted_capture_schema"] == TRUSTED_CAPTURE_SCHEMA


def test_hash_only_anchor_workflow_is_not_promotion_capable() -> None:
    get_bytes = _transport(_receipt(), _run(path=ANCHOR_WORKFLOW_PATH))
    with pytest.raises(ValueError, match="wrong workflow path"):
        fetch_trusted_capture_anchor_evidence(
            comment_id=_COMMENT_ID,
            batch_record=_batch(),
            get_bytes=get_bytes,
        )


def test_trusted_capture_dispatched_from_non_main_ref_fails_closed() -> None:
    get_bytes = _transport(_receipt(), _run(head_branch="dev/alternate"))
    with pytest.raises(ValueError, match="not dispatched from main"):
        fetch_trusted_capture_anchor_evidence(
            comment_id=_COMMENT_ID,
            batch_record=_batch(),
            get_bytes=get_bytes,
        )


def test_missing_trusted_capture_receipt_identity_fails_closed() -> None:
    get_bytes = _transport(_receipt(trusted=False), _run())
    with pytest.raises(ValueError, match="not trusted provider-capture evidence"):
        fetch_trusted_capture_anchor_evidence(
            comment_id=_COMMENT_ID,
            batch_record=_batch(),
            get_bytes=get_bytes,
        )


def test_trusted_workflow_has_only_routing_inputs_and_pinned_runtime_surface() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/prospective_provider_capture_anchor.yml"
    ).read_text(encoding="utf-8")
    inputs_block = workflow.split("    inputs:\n", 1)[1].split("\npermissions:", 1)[0]

    assert "schedule_date:" in inputs_block
    assert "sportradar_access_level:" in inputs_block
    for forbidden in (
        "batch_record_sha256",
        "batch_chain_head_sha256",
        "raw_payload_sha256",
        "manifest_sha256",
        "observed_at",
        "generated_at",
        "payload",
    ):
        assert forbidden not in inputs_block

    assert "SPORTRADAR_API_KEY: ${{ secrets.SPORTRADAR_API_KEY }}" in workflow
    assert "contents: read" in workflow
    assert "issues: write" in workflow
    assert "pip install" not in workflow
    assert 'python-version: "3.11.16"' in workflow
    assert "actions/checkout@11d5960a326750d5838078e36cf38b85af677262" in workflow
    assert "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065" in workflow
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in workflow
    assert "python -m tennis_genome.prospective.trusted_provider_capture" in workflow
    assert 'LEDGER_ISSUE_NUMBER: "111"' in workflow
    assert "trusted-provider-capture/" in workflow
