from __future__ import annotations

import copy
import json

import pytest

from tennis_genome.prospective.prediction_anchor_github import (
    ANCHOR_LEDGER_ISSUE,
    ANCHOR_REPOSITORY,
    ANCHOR_SCHEMA,
    ANCHOR_WORKFLOW_BLOB_SHA,
    ANCHOR_WORKFLOW_PATH,
    TRUSTED_ANCHOR_SCHEMA,
    TRUSTED_ANCHOR_VERSION,
    build_anchor_comment_body,
    fetch_authenticated_prediction_anchor_evidence,
    validate_retained_prediction_anchor_evidence,
)


def _receipt() -> dict[str, object]:
    run_id = 123456789
    return {
        "schema_version": ANCHOR_SCHEMA,
        "trusted_prediction_anchor_schema": TRUSTED_ANCHOR_SCHEMA,
        "provider": "GITHUB_ACTIONS",
        "repository": ANCHOR_REPOSITORY,
        "prediction_anchor_ledger_issue": ANCHOR_LEDGER_ISSUE,
        "prediction_anchor_workflow_version": TRUSTED_ANCHOR_VERSION,
        "workflow_source_sha": "d" * 40,
        "workflow_run_id": run_id,
        "workflow_run_attempt": 1,
        "workflow_run_url": (
            f"https://github.com/{ANCHOR_REPOSITORY}/actions/runs/{run_id}"
        ),
        "prediction_record_sha256": "a" * 64,
        "chain_head_sha256": "a" * 64,
        "runner_receipt_created_at_utc": "2026-09-15T14:00:30+00:00",
    }


def _comment(receipt: dict[str, object] | None = None) -> dict[str, object]:
    comment_id = 987654321
    return {
        "id": comment_id,
        "url": (
            f"https://api.github.com/repos/{ANCHOR_REPOSITORY}/issues/comments/"
            f"{comment_id}"
        ),
        "issue_url": (
            f"https://api.github.com/repos/{ANCHOR_REPOSITORY}/issues/"
            f"{ANCHOR_LEDGER_ISSUE}"
        ),
        "user": {"login": "github-actions[bot]", "type": "Bot"},
        "created_at": "2026-09-15T14:00:31Z",
        "updated_at": "2026-09-15T14:00:31Z",
        "body": build_anchor_comment_body(receipt or _receipt()),
    }


def _run(receipt: dict[str, object] | None = None) -> dict[str, object]:
    value = receipt or _receipt()
    run_id = int(value["workflow_run_id"])
    return {
        "id": run_id,
        "event": "workflow_dispatch",
        "status": "completed",
        "conclusion": "success",
        "path": ANCHOR_WORKFLOW_PATH,
        "head_branch": "main",
        "head_sha": value["workflow_source_sha"],
        "run_attempt": value["workflow_run_attempt"],
        "created_at": "2026-09-15T14:00:00Z",
        "html_url": f"https://github.com/{ANCHOR_REPOSITORY}/actions/runs/{run_id}",
        "repository": {"full_name": ANCHOR_REPOSITORY},
    }


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True).encode("utf-8")


def _fake_get(
    *,
    comment: dict[str, object] | None = None,
    run: dict[str, object] | None = None,
    source_sha: str = ANCHOR_WORKFLOW_BLOB_SHA,
):
    comment_value = comment or _comment()
    run_value = run or _run()

    def get_bytes(url: str) -> bytes:
        if "/issues/comments/" in url:
            return _json_bytes(comment_value)
        if "/actions/runs/" in url:
            return _json_bytes(run_value)
        if "/contents/" in url:
            return _json_bytes(
                {
                    "type": "file",
                    "path": ANCHOR_WORKFLOW_PATH,
                    "sha": source_sha,
                }
            )
        raise AssertionError(f"unexpected URL: {url}")

    return get_bytes


def test_live_prediction_anchor_authenticates_comment_run_and_source() -> None:
    evidence = fetch_authenticated_prediction_anchor_evidence(
        comment_id=987654321,
        expected_prediction_sha256="a" * 64,
        get_bytes=_fake_get(),
    )

    assert evidence.workflow_run_id == 123456789
    assert evidence.receipt["prediction_record_sha256"] == "a" * 64
    assert len(evidence.comment_response_sha256) == 64
    assert len(evidence.workflow_run_response_sha256) == 64


def test_retained_evidence_reproduces_without_network_source_check() -> None:
    comment_bytes = _json_bytes(_comment())
    run_bytes = _json_bytes(_run())

    evidence = validate_retained_prediction_anchor_evidence(
        comment_response_bytes=comment_bytes,
        workflow_run_response_bytes=run_bytes,
        expected_prediction_sha256="a" * 64,
    )

    assert evidence.comment_id == 987654321
    assert evidence.anchor_created_at.isoformat() == "2026-09-15T14:00:31+00:00"


def test_prediction_anchor_accepts_same_second_comment_precision() -> None:
    receipt = _receipt()
    receipt["runner_receipt_created_at_utc"] = "2026-09-15T14:00:30.750000+00:00"
    comment = _comment(receipt)
    comment["created_at"] = "2026-09-15T14:00:30Z"
    comment["updated_at"] = comment["created_at"]

    evidence = fetch_authenticated_prediction_anchor_evidence(
        comment_id=987654321,
        expected_prediction_sha256="a" * 64,
        get_bytes=_fake_get(comment=comment, run=_run(receipt)),
    )

    assert evidence.anchor_created_at.isoformat() == "2026-09-15T14:00:30+00:00"


def test_prediction_anchor_rejects_comment_from_previous_second() -> None:
    receipt = _receipt()
    receipt["runner_receipt_created_at_utc"] = "2026-09-15T14:00:30.000001+00:00"
    comment = _comment(receipt)
    comment["created_at"] = "2026-09-15T14:00:29Z"
    comment["updated_at"] = comment["created_at"]

    with pytest.raises(ValueError, match="predates runner receipt"):
        fetch_authenticated_prediction_anchor_evidence(
            comment_id=987654321,
            expected_prediction_sha256="a" * 64,
            get_bytes=_fake_get(comment=comment, run=_run(receipt)),
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value["user"].update({"login": "AidanDCM"}), "github-actions"),
        (lambda value: value.update({"updated_at": "2026-09-15T14:01:00Z"}), "edited"),
        (lambda value: value.update({"issue_url": "https://example.invalid"}), "ledger issue"),
    ],
)
def test_comment_identity_failures_are_rejected(mutation, message: str) -> None:
    comment = copy.deepcopy(_comment())
    mutation(comment)
    with pytest.raises(ValueError, match=message):
        fetch_authenticated_prediction_anchor_evidence(
            comment_id=987654321,
            expected_prediction_sha256="a" * 64,
            get_bytes=_fake_get(comment=comment),
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("event", "push", "workflow_dispatch"),
        ("head_branch", "dev/other", "main"),
        ("path", ".github/workflows/other.yml", "workflow path"),
        ("conclusion", "failure", "complete successfully"),
    ],
)
def test_workflow_identity_failures_are_rejected(
    field: str,
    value: object,
    message: str,
) -> None:
    run = copy.deepcopy(_run())
    run[field] = value
    with pytest.raises(ValueError, match=message):
        fetch_authenticated_prediction_anchor_evidence(
            comment_id=987654321,
            expected_prediction_sha256="a" * 64,
            get_bytes=_fake_get(run=run),
        )


def test_prediction_hash_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="retained prediction"):
        fetch_authenticated_prediction_anchor_evidence(
            comment_id=987654321,
            expected_prediction_sha256="b" * 64,
            get_bytes=_fake_get(),
        )


def test_source_blob_drift_is_rejected() -> None:
    with pytest.raises(ValueError, match="frozen blob"):
        fetch_authenticated_prediction_anchor_evidence(
            comment_id=987654321,
            expected_prediction_sha256="a" * 64,
            get_bytes=_fake_get(source_sha="f" * 40),
        )


def test_receipt_requires_prediction_to_be_immediate_chain_head() -> None:
    receipt = _receipt()
    receipt["chain_head_sha256"] = "b" * 64
    comment = _comment(receipt)
    run = _run(receipt)
    with pytest.raises(ValueError, match="immediate chain head"):
        fetch_authenticated_prediction_anchor_evidence(
            comment_id=987654321,
            expected_prediction_sha256="a" * 64,
            get_bytes=_fake_get(comment=comment, run=run),
        )
