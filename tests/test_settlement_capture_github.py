from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta

import pytest

from tennis_genome.prospective.settlement_capture_github import (
    SETTLEMENT_CAPTURE_SCHEMA,
    SETTLEMENT_CAPTURE_VERSION,
    SETTLEMENT_LEDGER_ISSUE,
    SETTLEMENT_PROVIDER,
    SETTLEMENT_REPOSITORY,
    SETTLEMENT_WORKFLOW_BLOB_SHA,
    SETTLEMENT_WORKFLOW_PATH,
    build_settlement_comment_body,
    fetch_authenticated_settlement_capture_evidence,
    validate_retained_settlement_capture_evidence,
)


def _receipt() -> dict[str, object]:
    run_id = 246813579
    return {
        "schema_version": SETTLEMENT_CAPTURE_SCHEMA,
        "settlement_capture_version": SETTLEMENT_CAPTURE_VERSION,
        "provider": SETTLEMENT_PROVIDER,
        "repository": SETTLEMENT_REPOSITORY,
        "settlement_ledger_issue": SETTLEMENT_LEDGER_ISSUE,
        "workflow_source_sha": "d" * 40,
        "workflow_run_id": run_id,
        "workflow_run_attempt": 1,
        "workflow_run_url": (
            f"https://github.com/{SETTLEMENT_REPOSITORY}/actions/runs/{run_id}"
        ),
        "prediction_record_sha256": "a" * 64,
        "identity_binding_sha256": "b" * 64,
        "sportradar_event_id": "sr:sport_event:123456",
        "sportradar_access_level": "trial",
        "provider_generated_at": "2026-09-15T15:00:00+00:00",
        "observed_at": "2026-09-15T15:00:30+00:00",
        "timeline_sha256": "c" * 64,
        "response_headers_sha256": "e" * 64,
        "provider_status": "ended",
        "winner_sportradar_id": "sr:competitor:11",
    }


def _comment(receipt: dict[str, object] | None = None) -> dict[str, object]:
    comment_id = 975318642
    return {
        "id": comment_id,
        "url": (
            f"https://api.github.com/repos/{SETTLEMENT_REPOSITORY}/issues/comments/"
            f"{comment_id}"
        ),
        "issue_url": (
            f"https://api.github.com/repos/{SETTLEMENT_REPOSITORY}/issues/"
            f"{SETTLEMENT_LEDGER_ISSUE}"
        ),
        "user": {"login": "github-actions[bot]", "type": "Bot"},
        "created_at": "2026-09-15T15:00:31Z",
        "updated_at": "2026-09-15T15:00:31Z",
        "body": build_settlement_comment_body(receipt or _receipt()),
    }


def _run(receipt: dict[str, object] | None = None) -> dict[str, object]:
    value = receipt or _receipt()
    run_id = int(value["workflow_run_id"])
    return {
        "id": run_id,
        "event": "workflow_dispatch",
        "status": "completed",
        "conclusion": "success",
        "path": SETTLEMENT_WORKFLOW_PATH,
        "head_branch": "main",
        "head_sha": value["workflow_source_sha"],
        "run_attempt": value["workflow_run_attempt"],
        "created_at": "2026-09-15T14:59:59Z",
        "html_url": (
            f"https://github.com/{SETTLEMENT_REPOSITORY}/actions/runs/{run_id}"
        ),
        "repository": {"full_name": SETTLEMENT_REPOSITORY},
    }


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True).encode("utf-8")


def _fake_get(
    *,
    comment: dict[str, object] | None = None,
    run: dict[str, object] | None = None,
    source_blob: str = SETTLEMENT_WORKFLOW_BLOB_SHA,
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
                    "path": SETTLEMENT_WORKFLOW_PATH,
                    "sha": source_blob,
                }
            )
        raise AssertionError(f"unexpected URL: {url}")

    return get_bytes


def test_live_settlement_capture_authenticates_comment_run_and_source() -> None:
    evidence = fetch_authenticated_settlement_capture_evidence(
        comment_id=975318642,
        expected_prediction_sha256="a" * 64,
        expected_identity_sha256="b" * 64,
        expected_event_id="sr:sport_event:123456",
        get_bytes=_fake_get(),
    )

    assert evidence.workflow_run_id == 246813579
    assert evidence.receipt["winner_sportradar_id"] == "sr:competitor:11"
    assert evidence.observed_at.isoformat() == "2026-09-15T15:00:30+00:00"


def test_retained_settlement_capture_reproduces_without_source_fetch() -> None:
    evidence = validate_retained_settlement_capture_evidence(
        comment_response_bytes=_json_bytes(_comment()),
        workflow_run_response_bytes=_json_bytes(_run()),
        expected_prediction_sha256="a" * 64,
        expected_identity_sha256="b" * 64,
        expected_event_id="sr:sport_event:123456",
    )
    assert evidence.comment_id == 975318642


def test_settlement_accepts_same_second_comment_precision() -> None:
    receipt = _receipt()
    receipt["observed_at"] = "2026-09-15T15:00:30.750000+00:00"
    comment = _comment(receipt)
    comment["created_at"] = "2026-09-15T15:00:30Z"
    comment["updated_at"] = comment["created_at"]

    evidence = fetch_authenticated_settlement_capture_evidence(
        comment_id=975318642,
        expected_prediction_sha256="a" * 64,
        expected_identity_sha256="b" * 64,
        expected_event_id="sr:sport_event:123456",
        get_bytes=_fake_get(comment=comment, run=_run(receipt)),
    )

    assert evidence.comment_created_at.isoformat() == "2026-09-15T15:00:30+00:00"


def test_settlement_rejects_comment_from_previous_second() -> None:
    receipt = _receipt()
    receipt["observed_at"] = "2026-09-15T15:00:30.000001+00:00"
    comment = _comment(receipt)
    comment["created_at"] = "2026-09-15T15:00:29Z"
    comment["updated_at"] = comment["created_at"]

    with pytest.raises(ValueError, match="predates runner observation"):
        fetch_authenticated_settlement_capture_evidence(
            comment_id=975318642,
            get_bytes=_fake_get(comment=comment, run=_run(receipt)),
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value["user"].update({"login": "AidanDCM"}), "github-actions"),
        (lambda value: value.update({"updated_at": "2026-09-15T15:01:00Z"}), "edited"),
        (lambda value: value.update({"issue_url": "https://example.invalid"}), "ledger issue"),
    ],
)
def test_settlement_comment_identity_failures_are_rejected(mutation, message: str) -> None:
    comment = copy.deepcopy(_comment())
    mutation(comment)
    with pytest.raises(ValueError, match=message):
        fetch_authenticated_settlement_capture_evidence(
            comment_id=975318642,
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
def test_settlement_workflow_identity_failures_are_rejected(
    field: str,
    value: object,
    message: str,
) -> None:
    run = copy.deepcopy(_run())
    run[field] = value
    with pytest.raises(ValueError, match=message):
        fetch_authenticated_settlement_capture_evidence(
            comment_id=975318642,
            get_bytes=_fake_get(run=run),
        )


def test_settlement_prediction_identity_and_event_mismatches_fail_closed() -> None:
    with pytest.raises(ValueError, match="prediction SHA"):
        fetch_authenticated_settlement_capture_evidence(
            comment_id=975318642,
            expected_prediction_sha256="f" * 64,
            get_bytes=_fake_get(),
        )
    with pytest.raises(ValueError, match="identity SHA"):
        fetch_authenticated_settlement_capture_evidence(
            comment_id=975318642,
            expected_identity_sha256="f" * 64,
            get_bytes=_fake_get(),
        )
    with pytest.raises(ValueError, match="event ID"):
        fetch_authenticated_settlement_capture_evidence(
            comment_id=975318642,
            expected_event_id="sr:sport_event:999",
            get_bytes=_fake_get(),
        )


def test_stale_provider_time_and_late_comment_are_rejected() -> None:
    receipt = _receipt()
    receipt["provider_generated_at"] = "2026-09-15T14:40:00+00:00"
    with pytest.raises(ValueError, match="stale"):
        fetch_authenticated_settlement_capture_evidence(
            comment_id=975318642,
            get_bytes=_fake_get(comment=_comment(receipt), run=_run(receipt)),
        )

    receipt = _receipt()
    comment = _comment(receipt)
    late = datetime.fromisoformat(str(receipt["observed_at"])) + timedelta(minutes=11)
    comment["created_at"] = late.isoformat().replace("+00:00", "Z")
    comment["updated_at"] = comment["created_at"]
    with pytest.raises(ValueError, match="too late"):
        fetch_authenticated_settlement_capture_evidence(
            comment_id=975318642,
            get_bytes=_fake_get(comment=comment, run=_run(receipt)),
        )


def test_settlement_source_blob_drift_is_rejected() -> None:
    with pytest.raises(ValueError, match="frozen blob"):
        fetch_authenticated_settlement_capture_evidence(
            comment_id=975318642,
            get_bytes=_fake_get(source_blob="f" * 40),
        )
