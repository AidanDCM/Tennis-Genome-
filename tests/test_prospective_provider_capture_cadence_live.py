from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tennis_genome.prospective.provider_batch import ProviderBatchStore
from tennis_genome.prospective.provider_batch_github_anchor import build_anchor_comment_body
from tennis_genome.prospective.provider_batch_pagination import capture_paginated_provider_batch
from tennis_genome.prospective.provider_capture_cadence_live import (
    LIVE_CADENCE_VERSION,
    LIVE_EVIDENCE_MODE,
    LiveProviderCaptureCadenceStore,
    attest_live_provider_batch,
    verify_live_capture_cadence,
)
from tennis_genome.prospective.trusted_capture_provenance import (
    TRUSTED_CAPTURE_FROZEN_BLOBS,
    trusted_capture_contents_url,
)
from tennis_genome.prospective.trusted_provider_capture import (
    TRUSTED_CAPTURE_SCHEMA,
    TRUSTED_CAPTURE_WORKFLOW_PATH,
)

_REPOSITORY = "AidanDCM/Tennis-Genome-"
_SOURCE_SHA = "d" * 40
_OLD_ANCHOR_WORKFLOW_PATH = ".github/workflows/prospective_provider_batch_anchor.yml"


def _capture(
    *,
    tmp_path: Path,
    store: ProviderBatchStore,
    observed_at: datetime,
    index: int,
) -> dict[str, object]:
    raw = tmp_path / f"live-page-{index}.json"
    headers = tmp_path / f"live-page-{index}.headers"
    raw.write_text(
        json.dumps(
            {"generated_at": observed_at.isoformat(), "summaries": []},
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    headers.write_text(
        "HTTP/2 200\nX-Max-Results: 0\nX-Offset: 0\nX-Result: 0\n",
        encoding="utf-8",
    )
    return capture_paginated_provider_batch(
        store=store,
        page_pairs=[(raw, headers)],
        schedule_date=observed_at.date(),
        observed_at=observed_at,
    )


def _live_payloads(
    *,
    batch: dict[str, object],
    comment_id: int,
    run_id: int,
    anchor_created_at: datetime,
    workflow_path: str = TRUSTED_CAPTURE_WORKFLOW_PATH,
) -> tuple[str, str, bytes, bytes]:
    run_created_at = anchor_created_at - timedelta(minutes=2)
    runner_receipt_created_at = anchor_created_at - timedelta(minutes=1)
    receipt = {
        "schema_version": "full-stack-forward-provider-batch-github-anchor-v1",
        "provider": "GITHUB_ACTIONS",
        "repository": _REPOSITORY,
        "workflow_source_sha": _SOURCE_SHA,
        "workflow_run_id": run_id,
        "workflow_run_attempt": 1,
        "workflow_run_url": f"https://github.com/{_REPOSITORY}/actions/runs/{run_id}",
        "batch_record_sha256": batch["record_sha256"],
        "batch_chain_head_sha256": batch["record_sha256"],
        "schedule_date": batch["schedule_date"],
        "raw_payload_sha256": batch["raw_payload_sha256"],
        "manifest_sha256": batch["manifest_sha256"],
        "observed_at": batch["observed_at"],
        "runner_receipt_created_at_utc": runner_receipt_created_at.isoformat(),
        "trusted_capture_schema": TRUSTED_CAPTURE_SCHEMA,
        "trusted_capture_receipt_sha256": "e" * 64,
        "sportradar_access_level": "production",
    }
    comment_url = f"https://api.github.com/repos/{_REPOSITORY}/issues/comments/{comment_id}"
    run_url = f"https://api.github.com/repos/{_REPOSITORY}/actions/runs/{run_id}"
    comment = {
        "id": comment_id,
        "url": comment_url,
        "issue_url": f"https://api.github.com/repos/{_REPOSITORY}/issues/111",
        "user": {"login": "github-actions[bot]", "type": "Bot"},
        "created_at": anchor_created_at.isoformat(),
        "updated_at": anchor_created_at.isoformat(),
        "body": build_anchor_comment_body(receipt),
    }
    run = {
        "id": run_id,
        "event": "workflow_dispatch",
        "status": "completed",
        "conclusion": "success",
        "path": workflow_path,
        "head_branch": "main",
        "head_sha": _SOURCE_SHA,
        "run_attempt": 1,
        "html_url": f"https://github.com/{_REPOSITORY}/actions/runs/{run_id}",
        "created_at": run_created_at.isoformat(),
        "repository": {"full_name": _REPOSITORY},
    }
    return (
        comment_url,
        run_url,
        json.dumps(comment, sort_keys=True).encode("utf-8"),
        json.dumps(run, sort_keys=True).encode("utf-8"),
    )


def _mutable_getter(payloads: dict[str, bytes]):
    source_payloads = {
        trusted_capture_contents_url(path=path, source_sha=_SOURCE_SHA): json.dumps(
            {"type": "file", "path": path, "sha": blob_sha},
            sort_keys=True,
        ).encode("utf-8")
        for path, blob_sha in TRUSTED_CAPTURE_FROZEN_BLOBS.items()
    }

    def get_bytes(url: str) -> bytes:
        if url in payloads:
            return payloads[url]
        if url in source_payloads:
            return source_payloads[url]
        raise ValueError(f"missing mocked GitHub object: {url}")

    return get_bytes


def test_live_attestation_retains_server_evidence_and_verifies_cadence(tmp_path: Path) -> None:
    batch_store = ProviderBatchStore(tmp_path / "batches")
    cadence_store = LiveProviderCaptureCadenceStore(tmp_path / "live-cadence")
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    batch = _capture(
        tmp_path=tmp_path,
        store=batch_store,
        observed_at=observed,
        index=1,
    )
    anchor = observed + timedelta(minutes=5)
    comment_url, run_url, comment_bytes, run_bytes = _live_payloads(
        batch=batch,
        comment_id=7001,
        run_id=8001,
        anchor_created_at=anchor,
    )
    payloads = {comment_url: comment_bytes, run_url: run_bytes}
    getter = _mutable_getter(payloads)

    record = attest_live_provider_batch(
        batch_store=batch_store,
        cadence_store=cadence_store,
        github_comment_id=7001,
        github_get_bytes=getter,
    )

    assert record["live_cadence_version"] == LIVE_CADENCE_VERSION
    assert record["anchor_evidence_mode"] == LIVE_EVIDENCE_MODE
    assert record["github_comment_id"] == 7001
    assert record["workflow_run_id"] == 8001
    assert record["github_comment_response_sha256"] == hashlib.sha256(comment_bytes).hexdigest()
    assert record["workflow_run_response_sha256"] == hashlib.sha256(run_bytes).hexdigest()
    for digest in record["evidence_sha256"]:
        assert (cadence_store.evidence_dir / digest).is_file()

    report = verify_live_capture_cadence(
        batch_store=batch_store,
        cadence_store=cadence_store,
        complete_through=anchor + timedelta(minutes=1),
        github_get_bytes=getter,
    )
    assert report["status"] == "LIVE_CADENCE_VERIFIED"
    assert report["attested_batch_count"] == 1


def test_hash_only_anchor_workflow_cannot_enter_live_cadence(tmp_path: Path) -> None:
    batch_store = ProviderBatchStore(tmp_path / "batches")
    cadence_store = LiveProviderCaptureCadenceStore(tmp_path / "live-cadence")
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    batch = _capture(tmp_path=tmp_path, store=batch_store, observed_at=observed, index=1)
    comment_url, run_url, comment_bytes, run_bytes = _live_payloads(
        batch=batch,
        comment_id=7099,
        run_id=8099,
        anchor_created_at=observed + timedelta(minutes=5),
        workflow_path=_OLD_ANCHOR_WORKFLOW_PATH,
    )
    getter = _mutable_getter({comment_url: comment_bytes, run_url: run_bytes})

    with pytest.raises(ValueError, match="wrong workflow path"):
        attest_live_provider_batch(
            batch_store=batch_store,
            cadence_store=cadence_store,
            github_comment_id=7099,
            github_get_bytes=getter,
        )


def test_source_blob_drift_fails_live_reverification(tmp_path: Path) -> None:
    batch_store = ProviderBatchStore(tmp_path / "batches")
    cadence_store = LiveProviderCaptureCadenceStore(tmp_path / "live-cadence")
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    batch = _capture(tmp_path=tmp_path, store=batch_store, observed_at=observed, index=1)
    anchor = observed + timedelta(minutes=5)
    comment_url, run_url, comment_bytes, run_bytes = _live_payloads(
        batch=batch,
        comment_id=7098,
        run_id=8098,
        anchor_created_at=anchor,
    )
    payloads = {comment_url: comment_bytes, run_url: run_bytes}
    normal_getter = _mutable_getter(payloads)
    attest_live_provider_batch(
        batch_store=batch_store,
        cadence_store=cadence_store,
        github_comment_id=7098,
        github_get_bytes=normal_getter,
    )

    drift_path = "src/tennis_genome/prospective/provider_batch_pagination.py"
    drift_url = trusted_capture_contents_url(path=drift_path, source_sha=_SOURCE_SHA)

    def drift_getter(url: str) -> bytes:
        if url == drift_url:
            return json.dumps(
                {"type": "file", "path": drift_path, "sha": "f" * 40},
                sort_keys=True,
            ).encode("utf-8")
        return normal_getter(url)

    with pytest.raises(ValueError, match="blob differs from frozen identity"):
        cadence_store.verify(batch_store=batch_store, github_get_bytes=drift_getter)


def test_later_comment_edit_fails_live_reverification(tmp_path: Path) -> None:
    batch_store = ProviderBatchStore(tmp_path / "batches")
    cadence_store = LiveProviderCaptureCadenceStore(tmp_path / "live-cadence")
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    batch = _capture(tmp_path=tmp_path, store=batch_store, observed_at=observed, index=1)
    anchor = observed + timedelta(minutes=5)
    comment_url, run_url, comment_bytes, run_bytes = _live_payloads(
        batch=batch,
        comment_id=7002,
        run_id=8002,
        anchor_created_at=anchor,
    )
    payloads = {comment_url: comment_bytes, run_url: run_bytes}
    getter = _mutable_getter(payloads)
    attest_live_provider_batch(
        batch_store=batch_store,
        cadence_store=cadence_store,
        github_comment_id=7002,
        github_get_bytes=getter,
    )

    edited = json.loads(comment_bytes)
    edited["updated_at"] = (anchor + timedelta(minutes=1)).isoformat()
    payloads[comment_url] = json.dumps(edited, sort_keys=True).encode("utf-8")

    with pytest.raises(ValueError, match="has been edited"):
        cadence_store.verify(batch_store=batch_store, github_get_bytes=getter)


def test_deleted_live_comment_fails_closed(tmp_path: Path) -> None:
    batch_store = ProviderBatchStore(tmp_path / "batches")
    cadence_store = LiveProviderCaptureCadenceStore(tmp_path / "live-cadence")
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    batch = _capture(tmp_path=tmp_path, store=batch_store, observed_at=observed, index=1)
    anchor = observed + timedelta(minutes=5)
    comment_url, run_url, comment_bytes, run_bytes = _live_payloads(
        batch=batch,
        comment_id=7003,
        run_id=8003,
        anchor_created_at=anchor,
    )
    payloads = {comment_url: comment_bytes, run_url: run_bytes}
    getter = _mutable_getter(payloads)
    attest_live_provider_batch(
        batch_store=batch_store,
        cadence_store=cadence_store,
        github_comment_id=7003,
        github_get_bytes=getter,
    )
    del payloads[comment_url]

    with pytest.raises(ValueError, match="missing mocked GitHub object"):
        cadence_store.verify(batch_store=batch_store, github_get_bytes=getter)


def test_retained_live_api_bytes_are_hash_checked(tmp_path: Path) -> None:
    batch_store = ProviderBatchStore(tmp_path / "batches")
    cadence_store = LiveProviderCaptureCadenceStore(tmp_path / "live-cadence")
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    batch = _capture(tmp_path=tmp_path, store=batch_store, observed_at=observed, index=1)
    anchor = observed + timedelta(minutes=5)
    comment_url, run_url, comment_bytes, run_bytes = _live_payloads(
        batch=batch,
        comment_id=7004,
        run_id=8004,
        anchor_created_at=anchor,
    )
    payloads = {comment_url: comment_bytes, run_url: run_bytes}
    getter = _mutable_getter(payloads)
    record = attest_live_provider_batch(
        batch_store=batch_store,
        cadence_store=cadence_store,
        github_comment_id=7004,
        github_get_bytes=getter,
    )
    comment_sha = str(record["github_comment_response_sha256"])
    (cadence_store.evidence_dir / comment_sha).write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="retained live cadence evidence digest mismatch"):
        cadence_store.verify(batch_store=batch_store, github_get_bytes=getter)


def test_first_live_attestation_must_target_current_provider_chain_head(tmp_path: Path) -> None:
    batch_store = ProviderBatchStore(tmp_path / "batches")
    cadence_store = LiveProviderCaptureCadenceStore(tmp_path / "live-cadence")
    first_time = datetime(2026, 9, 15, 12, tzinfo=UTC)
    first = _capture(
        tmp_path=tmp_path,
        store=batch_store,
        observed_at=first_time,
        index=1,
    )
    _capture(
        tmp_path=tmp_path,
        store=batch_store,
        observed_at=first_time + timedelta(minutes=20),
        index=2,
    )
    comment_url, run_url, comment_bytes, run_bytes = _live_payloads(
        batch=first,
        comment_id=7005,
        run_id=8005,
        anchor_created_at=first_time + timedelta(minutes=5),
    )
    getter = _mutable_getter({comment_url: comment_bytes, run_url: run_bytes})

    with pytest.raises(ValueError, match="current provider-batch chain head"):
        attest_live_provider_batch(
            batch_store=batch_store,
            cadence_store=cadence_store,
            github_comment_id=7005,
            github_get_bytes=getter,
        )
