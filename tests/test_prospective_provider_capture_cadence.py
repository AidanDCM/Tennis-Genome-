from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tennis_genome.prospective.provider_batch import ProviderBatchStore, capture_provider_batch
from tennis_genome.prospective.provider_capture_cadence import (
    ProviderCaptureCadenceStore,
    attest_provider_batch,
    verify_capture_cadence,
)


def _write_payload(path: Path) -> Path:
    path.write_text(
        json.dumps({"summaries": []}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _capture(
    *,
    tmp_path: Path,
    store: ProviderBatchStore,
    observed_at: datetime,
    index: int,
) -> dict[str, object]:
    payload = _write_payload(tmp_path / f"batch-{index}.json")
    return capture_provider_batch(
        store=store,
        raw_payload_path=payload,
        schedule_date=observed_at.date(),
        observed_at=observed_at,
    )


def _anchor_files(
    *,
    tmp_path: Path,
    batch: dict[str, object],
    run_id: int,
    anchor_created_at: datetime,
    index: int,
) -> tuple[Path, Path]:
    source_sha = "d" * 40
    receipt = {
        "schema_version": "full-stack-forward-provider-batch-github-anchor-v1",
        "provider": "GITHUB_ACTIONS",
        "repository": "AidanDCM/Tennis-Genome-",
        "workflow_source_sha": source_sha,
        "workflow_run_id": run_id,
        "workflow_run_attempt": 1,
        "workflow_run_url": (
            f"https://github.com/AidanDCM/Tennis-Genome-/actions/runs/{run_id}"
        ),
        "batch_record_sha256": batch["record_sha256"],
        "batch_chain_head_sha256": batch["record_sha256"],
        "schedule_date": batch["schedule_date"],
        "raw_payload_sha256": batch["raw_payload_sha256"],
        "manifest_sha256": batch["manifest_sha256"],
        "observed_at": batch["observed_at"],
        "runner_receipt_created_at_utc": (anchor_created_at + timedelta(minutes=1)).isoformat(),
    }
    run = {
        "id": run_id,
        "event": "workflow_dispatch",
        "status": "completed",
        "conclusion": "success",
        "path": ".github/workflows/prospective_provider_batch_anchor.yml",
        "head_sha": source_sha,
        "created_at": anchor_created_at.isoformat(),
        "repository": {"full_name": "AidanDCM/Tennis-Genome-"},
    }
    receipt_path = tmp_path / f"receipt-{index}.json"
    run_path = tmp_path / f"run-{index}.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    run_path.write_text(
        json.dumps(run, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt_path, run_path


def _attest(
    *,
    tmp_path: Path,
    batch_store: ProviderBatchStore,
    cadence_store: ProviderCaptureCadenceStore,
    batch: dict[str, object],
    run_id: int,
    anchor_created_at: datetime,
    index: int,
) -> dict[str, object]:
    receipt_path, run_path = _anchor_files(
        tmp_path=tmp_path,
        batch=batch,
        run_id=run_id,
        anchor_created_at=anchor_created_at,
        index=index,
    )
    return attest_provider_batch(
        batch_store=batch_store,
        cadence_store=cadence_store,
        anchor_receipt_path=receipt_path,
        workflow_run_metadata_path=run_path,
    )


def test_attestation_rederives_batch_identity_and_server_time(tmp_path: Path) -> None:
    batch_store = ProviderBatchStore(tmp_path / "batches")
    cadence_store = ProviderCaptureCadenceStore(tmp_path / "cadence")
    observed = datetime(2026, 9, 15, 0, tzinfo=UTC)
    batch = _capture(tmp_path=tmp_path, store=batch_store, observed_at=observed, index=1)
    anchor = observed + timedelta(minutes=5)

    record = _attest(
        tmp_path=tmp_path,
        batch_store=batch_store,
        cadence_store=cadence_store,
        batch=batch,
        run_id=1001,
        anchor_created_at=anchor,
        index=1,
    )

    assert record["batch_record_sha256"] == batch["record_sha256"]
    assert record["anchor_created_at"] == anchor.isoformat()
    report = cadence_store.verify(batch_store=batch_store)
    assert report["status"] == "VERIFIED"
    assert report["attested_batch_count"] == 1


def test_anchor_more_than_thirty_minutes_after_observation_is_rejected(tmp_path: Path) -> None:
    batch_store = ProviderBatchStore(tmp_path / "batches")
    cadence_store = ProviderCaptureCadenceStore(tmp_path / "cadence")
    observed = datetime(2026, 9, 15, 6, tzinfo=UTC)
    batch = _capture(tmp_path=tmp_path, store=batch_store, observed_at=observed, index=1)

    with pytest.raises(ValueError, match="too long after provider observation"):
        _attest(
            tmp_path=tmp_path,
            batch_store=batch_store,
            cadence_store=cadence_store,
            batch=batch,
            run_id=1002,
            anchor_created_at=observed + timedelta(minutes=31),
            index=1,
        )


def test_four_attested_captures_cover_daily_six_hour_cadence(tmp_path: Path) -> None:
    batch_store = ProviderBatchStore(tmp_path / "batches")
    cadence_store = ProviderCaptureCadenceStore(tmp_path / "cadence")
    base = datetime(2026, 9, 15, 0, tzinfo=UTC)

    for index, hour in enumerate((0, 6, 12, 18), start=1):
        observed = base + timedelta(hours=hour)
        batch = _capture(
            tmp_path=tmp_path,
            store=batch_store,
            observed_at=observed,
            index=index,
        )
        _attest(
            tmp_path=tmp_path,
            batch_store=batch_store,
            cadence_store=cadence_store,
            batch=batch,
            run_id=1100 + index,
            anchor_created_at=observed + timedelta(minutes=5),
            index=index,
        )

    report = verify_capture_cadence(
        batch_store=batch_store,
        cadence_store=cadence_store,
        complete_through=base + timedelta(hours=23, minutes=59),
    )
    assert report["status"] == "CADENCE_VERIFIED"
    assert report["attested_batch_count"] == 4
    assert report["covered_schedule_date_count"] == 1


def test_gap_over_seven_hours_fails_closed(tmp_path: Path) -> None:
    batch_store = ProviderBatchStore(tmp_path / "batches")
    cadence_store = ProviderCaptureCadenceStore(tmp_path / "cadence")
    base = datetime(2026, 9, 15, 0, tzinfo=UTC)

    for index, hour in enumerate((0, 8), start=1):
        observed = base + timedelta(hours=hour)
        batch = _capture(
            tmp_path=tmp_path,
            store=batch_store,
            observed_at=observed,
            index=index,
        )
        _attest(
            tmp_path=tmp_path,
            batch_store=batch_store,
            cadence_store=cadence_store,
            batch=batch,
            run_id=1200 + index,
            anchor_created_at=observed + timedelta(minutes=5),
            index=index,
        )

    with pytest.raises(ValueError, match="gap exceeds seven hours"):
        verify_capture_cadence(
            batch_store=batch_store,
            cadence_store=cadence_store,
            complete_through=base + timedelta(hours=8, minutes=10),
        )


def test_due_unanchored_batch_fails_closed(tmp_path: Path) -> None:
    batch_store = ProviderBatchStore(tmp_path / "batches")
    cadence_store = ProviderCaptureCadenceStore(tmp_path / "cadence")
    base = datetime(2026, 9, 15, 0, tzinfo=UTC)

    first = _capture(tmp_path=tmp_path, store=batch_store, observed_at=base, index=1)
    _attest(
        tmp_path=tmp_path,
        batch_store=batch_store,
        cadence_store=cadence_store,
        batch=first,
        run_id=1301,
        anchor_created_at=base + timedelta(minutes=5),
        index=1,
    )
    _capture(
        tmp_path=tmp_path,
        store=batch_store,
        observed_at=base + timedelta(hours=6),
        index=2,
    )

    with pytest.raises(ValueError, match="lack external cadence attestation"):
        verify_capture_cadence(
            batch_store=batch_store,
            cadence_store=cadence_store,
            complete_through=base + timedelta(hours=6, minutes=10),
        )


def test_wrong_workflow_event_is_rejected(tmp_path: Path) -> None:
    batch_store = ProviderBatchStore(tmp_path / "batches")
    cadence_store = ProviderCaptureCadenceStore(tmp_path / "cadence")
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    batch = _capture(tmp_path=tmp_path, store=batch_store, observed_at=observed, index=1)
    receipt_path, run_path = _anchor_files(
        tmp_path=tmp_path,
        batch=batch,
        run_id=1401,
        anchor_created_at=observed + timedelta(minutes=5),
        index=1,
    )
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["event"] = "push"
    run_path.write_text(json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="workflow_dispatch"):
        attest_provider_batch(
            batch_store=batch_store,
            cadence_store=cadence_store,
            anchor_receipt_path=receipt_path,
            workflow_run_metadata_path=run_path,
        )


def test_retained_anchor_evidence_tampering_is_detected(tmp_path: Path) -> None:
    batch_store = ProviderBatchStore(tmp_path / "batches")
    cadence_store = ProviderCaptureCadenceStore(tmp_path / "cadence")
    observed = datetime(2026, 9, 15, 18, tzinfo=UTC)
    batch = _capture(tmp_path=tmp_path, store=batch_store, observed_at=observed, index=1)
    record = _attest(
        tmp_path=tmp_path,
        batch_store=batch_store,
        cadence_store=cadence_store,
        batch=batch,
        run_id=1501,
        anchor_created_at=observed + timedelta(minutes=5),
        index=1,
    )
    receipt_sha = str(record["anchor_receipt_sha256"])
    (cadence_store.evidence_dir / receipt_sha).write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="cadence evidence digest mismatch"):
        cadence_store.verify(batch_store=batch_store)
