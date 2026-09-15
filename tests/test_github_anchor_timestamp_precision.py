from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tennis_genome.prospective.provider_batch_github_anchor import (
    _validate_workflow_run,
)
from tennis_genome.prospective.trusted_provider_capture import (
    TRUSTED_CAPTURE_WORKFLOW_PATH,
)


def _payloads(*, runner_receipt_created_at: datetime):
    anchor_created_at = datetime(2026, 9, 15, 16, 52, 49, tzinfo=UTC)
    run_id = 34997744882
    source_sha = "e176d4e5a9d2451a7a46b0ebcd66837b40504ffc"
    receipt = {
        "workflow_run_id": run_id,
        "workflow_run_attempt": 1,
        "workflow_source_sha": source_sha,
        "runner_receipt_created_at_utc": runner_receipt_created_at.isoformat(),
    }
    run = {
        "id": run_id,
        "repository": {"full_name": "AidanDCM/Tennis-Genome-"},
        "event": "workflow_dispatch",
        "status": "completed",
        "conclusion": "success",
        "path": TRUSTED_CAPTURE_WORKFLOW_PATH,
        "head_branch": "main",
        "head_sha": source_sha,
        "run_attempt": 1,
        "html_url": f"https://github.com/AidanDCM/Tennis-Genome-/actions/runs/{run_id}",
        "created_at": "2026-09-15T16:52:41Z",
    }
    return receipt, run, anchor_created_at


def test_runner_receipt_later_within_same_github_second_is_valid() -> None:
    receipt, run, anchor = _payloads(
        runner_receipt_created_at=datetime(
            2026, 9, 15, 16, 52, 49, 405862, tzinfo=UTC
        )
    )
    _validate_workflow_run(
        run=run,
        receipt=receipt,
        anchor_created_at=anchor,
        expected_workflow_path=TRUSTED_CAPTURE_WORKFLOW_PATH,
        require_main_ref=True,
    )


def test_runner_receipt_in_later_github_second_still_fails_closed() -> None:
    receipt, run, anchor = _payloads(
        runner_receipt_created_at=datetime(2026, 9, 15, 16, 52, 50, tzinfo=UTC)
    )
    with pytest.raises(ValueError, match="anchor predates runner receipt"):
        _validate_workflow_run(
            run=run,
            receipt=receipt,
            anchor_created_at=anchor,
            expected_workflow_path=TRUSTED_CAPTURE_WORKFLOW_PATH,
            require_main_ref=True,
        )
