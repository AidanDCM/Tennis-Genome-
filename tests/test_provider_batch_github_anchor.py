from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tennis_genome.prospective.provider_batch_github_anchor import (
    ANCHOR_BOT_LOGIN,
    ANCHOR_COMMENT_MARKER,
    ANCHOR_LEDGER_ISSUE,
    ANCHOR_RECEIPT_SCHEMA,
    ANCHOR_REPOSITORY,
    ANCHOR_WORKFLOW_PATH,
    build_anchor_comment_body,
    fetch_live_anchor_evidence,
)
from tennis_genome.prospective.provider_batch_pagination import PAGINATION_SCHEMA

COMMENT_ID = 123456789
RUN_ID = 987654321
SOURCE_SHA = "d" * 40


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


def _receipt() -> dict[str, object]:
    batch = _batch()
    return {
        "schema_version": ANCHOR_RECEIPT_SCHEMA,
        "provider": "GITHUB_ACTIONS",
        "repository": ANCHOR_REPOSITORY,
        "workflow_source_sha": SOURCE_SHA,
        "workflow_run_id": RUN_ID,
        "workflow_run_attempt": 1,
        "workflow_run_url": f"https://github.com/{ANCHOR_REPOSITORY}/actions/runs/{RUN_ID}",
        "batch_record_sha256": batch["record_sha256"],
        "batch_chain_head_sha256": batch["record_sha256"],
        "schedule_date": batch["schedule_date"],
        "raw_payload_sha256": batch["raw_payload_sha256"],
        "manifest_sha256": batch["manifest_sha256"],
        "observed_at": batch["observed_at"],
        "runner_receipt_created_at_utc": "2026-09-15T12:03:00+00:00",
    }


def _comment(
    *,
    receipt: dict[str, object] | None = None,
    created_at: str = "2026-09-15T12:05:00+00:00",
    updated_at: str | None = None,
    actor: str = ANCHOR_BOT_LOGIN,
    actor_type: str = "Bot",
    issue_number: int = ANCHOR_LEDGER_ISSUE,
) -> dict[str, object]:
    actual_receipt = receipt or _receipt()
    return {
        "id": COMMENT_ID,
        "url": (
            f"https://api.github.com/repos/{ANCHOR_REPOSITORY}/issues/comments/{COMMENT_ID}"
        ),
        "issue_url": (
            f"https://api.github.com/repos/{ANCHOR_REPOSITORY}/issues/{issue_number}"
        ),
        "body": build_anchor_comment_body(actual_receipt),
        "user": {"login": actor, "type": actor_type},
        "created_at": created_at,
        "updated_at": updated_at or created_at,
    }


def _run(
    *,
    event: str = "workflow_dispatch",
    status: str = "completed",
    conclusion: str = "success",
    head_sha: str = SOURCE_SHA,
    path: str = ANCHOR_WORKFLOW_PATH,
) -> dict[str, object]:
    return {
        "id": RUN_ID,
        "run_attempt": 1,
        "event": event,
        "status": status,
        "conclusion": conclusion,
        "path": path,
        "head_sha": head_sha,
        "html_url": f"https://github.com/{ANCHOR_REPOSITORY}/actions/runs/{RUN_ID}",
        "created_at": "2026-09-15T12:02:00+00:00",
        "repository": {"full_name": ANCHOR_REPOSITORY},
    }


def _bytes(value: dict[str, object]) -> bytes:
    return (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")


def _transport(
    comment: dict[str, object],
    run: dict[str, object],
) -> tuple[Callable[[str], bytes], bytes, bytes]:
    comment_bytes = _bytes(comment)
    run_bytes = _bytes(run)
    comment_url = (
        f"https://api.github.com/repos/{ANCHOR_REPOSITORY}/issues/comments/{COMMENT_ID}"
    )
    run_url = f"https://api.github.com/repos/{ANCHOR_REPOSITORY}/actions/runs/{RUN_ID}"

    def get_bytes(url: str) -> bytes:
        if url == comment_url:
            return comment_bytes
        if url == run_url:
            return run_bytes
        raise AssertionError(f"unexpected GitHub API URL: {url}")

    return get_bytes, comment_bytes, run_bytes


def test_valid_live_github_anchor_uses_server_comment_time_and_retains_hashes() -> None:
    get_bytes, comment_bytes, run_bytes = _transport(_comment(), _run())

    evidence = fetch_live_anchor_evidence(
        comment_id=COMMENT_ID,
        batch_record=_batch(),
        get_bytes=get_bytes,
    )

    assert evidence.comment_id == COMMENT_ID
    assert evidence.workflow_run_id == RUN_ID
    assert evidence.anchor_created_at == datetime(2026, 9, 15, 12, 5, tzinfo=UTC)
    assert evidence.comment_response_bytes == comment_bytes
    assert evidence.workflow_run_response_bytes == run_bytes
    assert evidence.comment_response_sha256 == hashlib.sha256(comment_bytes).hexdigest()
    assert evidence.workflow_run_response_sha256 == hashlib.sha256(run_bytes).hexdigest()


@pytest.mark.parametrize(
    ("actor", "actor_type"),
    [("AidanDCM", "User"), ("other-bot[bot]", "Bot"), (ANCHOR_BOT_LOGIN, "User")],
)
def test_wrong_anchor_comment_actor_fails_closed(actor: str, actor_type: str) -> None:
    get_bytes, _, _ = _transport(
        _comment(actor=actor, actor_type=actor_type),
        _run(),
    )

    with pytest.raises(ValueError, match="github-actions"):
        fetch_live_anchor_evidence(comment_id=COMMENT_ID, get_bytes=get_bytes)


def test_edited_anchor_comment_fails_closed() -> None:
    get_bytes, _, _ = _transport(
        _comment(updated_at="2026-09-15T12:06:00+00:00"),
        _run(),
    )

    with pytest.raises(ValueError, match="has been edited"):
        fetch_live_anchor_evidence(comment_id=COMMENT_ID, get_bytes=get_bytes)


def test_anchor_comment_on_wrong_issue_fails_closed() -> None:
    get_bytes, _, _ = _transport(
        _comment(issue_number=ANCHOR_LEDGER_ISSUE + 1),
        _run(),
    )

    with pytest.raises(ValueError, match="frozen ledger issue"):
        fetch_live_anchor_evidence(comment_id=COMMENT_ID, get_bytes=get_bytes)


def test_coherently_tampered_comment_batch_hash_fails_against_retained_batch() -> None:
    receipt = _receipt()
    receipt["batch_record_sha256"] = "e" * 64
    receipt["batch_chain_head_sha256"] = "e" * 64
    get_bytes, _, _ = _transport(_comment(receipt=receipt), _run())

    with pytest.raises(ValueError, match="batch record SHA differs"):
        fetch_live_anchor_evidence(
            comment_id=COMMENT_ID,
            batch_record=_batch(),
            get_bytes=get_bytes,
        )


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"event": "push"}, "workflow_dispatch"),
        ({"status": "in_progress"}, "complete successfully"),
        ({"conclusion": "failure"}, "complete successfully"),
        ({"head_sha": "e" * 40}, "source SHA differs"),
        ({"path": ".github/workflows/other.yml"}, "wrong workflow path"),
    ],
)
def test_wrong_live_workflow_run_fails_closed(
    override: dict[str, str],
    message: str,
) -> None:
    run = _run(**override)
    get_bytes, _, _ = _transport(_comment(), run)

    with pytest.raises(ValueError, match=message):
        fetch_live_anchor_evidence(comment_id=COMMENT_ID, get_bytes=get_bytes)


def test_live_comment_before_newest_provider_generation_fails_closed() -> None:
    receipt = _receipt()
    receipt["runner_receipt_created_at_utc"] = "2026-09-15T11:56:00+00:00"
    run = _run()
    run["created_at"] = "2026-09-15T11:55:00+00:00"
    get_bytes, _, _ = _transport(
        _comment(receipt=receipt, created_at="2026-09-15T11:57:00+00:00"),
        run,
    )

    with pytest.raises(ValueError, match="predates newest provider generation"):
        fetch_live_anchor_evidence(
            comment_id=COMMENT_ID,
            batch_record=_batch(),
            get_bytes=get_bytes,
        )


def test_live_comment_more_than_thirty_minutes_after_oldest_provider_page_fails_closed() -> None:
    get_bytes, _, _ = _transport(
        _comment(created_at="2026-09-15T12:26:00+00:00"),
        _run(),
    )

    with pytest.raises(ValueError, match="too late for retained provider page set"):
        fetch_live_anchor_evidence(
            comment_id=COMMENT_ID,
            batch_record=_batch(),
            get_bytes=get_bytes,
        )


def test_noncanonical_comment_receipt_fails_closed() -> None:
    comment = _comment()
    receipt = _receipt()
    pretty = json.dumps(receipt, indent=2, sort_keys=True)
    comment["body"] = f"{ANCHOR_COMMENT_MARKER}\n```json\n{pretty}\n```"
    get_bytes, _, _ = _transport(comment, _run())

    with pytest.raises(ValueError, match="not canonical JSON"):
        fetch_live_anchor_evidence(comment_id=COMMENT_ID, get_bytes=get_bytes)


def test_workflow_is_permission_minimized_and_publishes_to_frozen_ledger() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/prospective_provider_batch_anchor.yml"
    ).read_text(encoding="utf-8")

    assert "contents: read" in workflow
    assert "issues: write" in workflow
    assert 'LEDGER_ISSUE_NUMBER: "111"' in workflow
    assert ANCHOR_COMMENT_MARKER in workflow
    assert "provider_batch_anchor_comment.json" in workflow
