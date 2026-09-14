from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from tennis_genome.prospective.census import EventCensusStore, record_discovery
from tennis_genome.prospective.provider_batch import ProviderBatchStore, capture_provider_batch
from tennis_genome.prospective.provider_batch_anchor import (
    ANCHOR_SCHEMA,
    ANCHOR_WORKFLOW_PATH,
    ProviderBatchAnchorStore,
    attest_batch_anchor,
    reconcile_anchored_batches_with_census,
    verify_capture_cadence,
)


def _summary(event_id: str, *, start: datetime) -> dict[str, object]:
    return {
        "sport_event": {
            "id": event_id,
            "start_time": start.isoformat(),
            "start_time_confirmed": True,
            "sport_event_context": {
                "category": {"id": "sr:category:3", "name": "ATP"},
                "competition": {
                    "id": f"sr:competition:{event_id.rsplit(':', 1)[-1]}",
                    "name": "Test Competition",
                    "type": "singles",
                },
            },
            "competitors": [],
        },
        "sport_event_status": {"status": "not_started"},
    }


def _capture(
    tmp_path: Path,
    store: ProviderBatchStore,
    *,
    schedule_date: date,
    observed_at: datetime,
    summaries: list[dict[str, object]],
    name: str,
) -> dict[str, object]:
    path = tmp_path / name
    path.write_text(
        json.dumps({"summaries": summaries}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return capture_provider_batch(
        store=store,
        raw_payload_path=path,
        schedule_date=schedule_date,
        observed_at=observed_at,
    )


def _anchor_evidence(
    tmp_path: Path,
    batch: dict[str, object],
    *,
    created_at: datetime,
    suffix: str,
    run_id: int,
    head_branch: str = "main",
    receipt_overrides: dict[str, object] | None = None,
) -> tuple[Path, Path]:
    workflow_sha = "a" * 40
    receipt: dict[str, object] = {
        "schema_version": ANCHOR_SCHEMA,
        "provider": "GITHUB_ACTIONS",
        "repository": "AidanDCM/Tennis-Genome-",
        "workflow_source_sha": workflow_sha,
        "workflow_run_id": run_id,
        "workflow_run_attempt": 1,
        "workflow_run_url": f"https://github.com/AidanDCM/Tennis-Genome-/actions/runs/{run_id}",
        "batch_record_sha256": batch["record_sha256"],
        "batch_chain_head_sha256": batch["record_sha256"],
        "schedule_date": batch["schedule_date"],
        "observed_at": batch["observed_at"],
        "raw_payload_sha256": batch["raw_payload_sha256"],
        "manifest_sha256": batch["manifest_sha256"],
        "runner_receipt_created_at_utc": (created_at + timedelta(seconds=5)).isoformat(),
    }
    if receipt_overrides:
        receipt.update(receipt_overrides)
    run = {
        "id": run_id,
        "event": "workflow_dispatch",
        "status": "completed",
        "conclusion": "success",
        "path": ANCHOR_WORKFLOW_PATH,
        "head_branch": head_branch,
        "head_sha": workflow_sha,
        "created_at": created_at.isoformat(),
        "repository": {"full_name": "AidanDCM/Tennis-Genome-"},
    }
    receipt_path = tmp_path / f"receipt-{suffix}.json"
    run_path = tmp_path / f"run-{suffix}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    run_path.write_text(json.dumps(run, indent=2, sort_keys=True) + "\n")
    return receipt_path, run_path


def _attest(
    tmp_path: Path,
    anchor_store: ProviderBatchAnchorStore,
    batch_store: ProviderBatchStore,
    batch: dict[str, object],
    *,
    created_at: datetime,
    suffix: str,
    run_id: int,
) -> dict[str, object]:
    receipt, run = _anchor_evidence(
        tmp_path,
        batch,
        created_at=created_at,
        suffix=suffix,
        run_id=run_id,
    )
    return attest_batch_anchor(
        store=anchor_store,
        batch_store=batch_store,
        batch_record_sha256=str(batch["record_sha256"]),
        anchor_receipt_path=receipt,
        github_run_metadata_path=run,
    )


def _record_census(
    tmp_path: Path,
    store: EventCensusStore,
    *,
    event_id: str,
    observed_at: datetime,
    scheduled_start: datetime,
) -> None:
    path = tmp_path / f"census-{event_id.rsplit(':', 1)[-1]}.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "full-stack-forward-census-discovery-v1",
                "provider": "SPORTRADAR",
                "provider_event_id": event_id,
                "tour": "ATP",
                "event_type": "SINGLES",
                "observed_at": observed_at.isoformat(),
                "scheduled_start": scheduled_start.isoformat(),
                "match_id": None,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    record_discovery(store=store, discovery_evidence_path=path)


def _anchor_two_dates_for_slot(
    tmp_path: Path,
    *,
    batch_store: ProviderBatchStore,
    anchor_store: ProviderBatchAnchorStore,
    slot: datetime,
    current_summaries: list[dict[str, object]] | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    current = _capture(
        tmp_path,
        batch_store,
        schedule_date=slot.date(),
        observed_at=slot + timedelta(minutes=10),
        summaries=current_summaries or [],
        name=f"current-{slot.hour}.json",
    )
    _attest(
        tmp_path,
        anchor_store,
        batch_store,
        current,
        created_at=slot + timedelta(minutes=20),
        suffix=f"current-{slot.hour}",
        run_id=1000 + slot.hour,
    )
    next_day = _capture(
        tmp_path,
        batch_store,
        schedule_date=slot.date() + timedelta(days=1),
        observed_at=slot + timedelta(minutes=25),
        summaries=[],
        name=f"next-{slot.hour}.json",
    )
    _attest(
        tmp_path,
        anchor_store,
        batch_store,
        next_day,
        created_at=slot + timedelta(minutes=35),
        suffix=f"next-{slot.hour}",
        run_id=2000 + slot.hour,
    )
    return current, next_day


def test_anchor_attestation_reproduces_from_github_server_metadata(tmp_path: Path) -> None:
    slot = datetime(2026, 9, 15, 0, tzinfo=UTC)
    batch_store = ProviderBatchStore(tmp_path / "batches")
    anchor_store = ProviderBatchAnchorStore(tmp_path / "anchors")
    batch = _capture(
        tmp_path,
        batch_store,
        schedule_date=slot.date(),
        observed_at=slot + timedelta(minutes=5),
        summaries=[],
        name="batch.json",
    )
    record = _attest(
        tmp_path,
        anchor_store,
        batch_store,
        batch,
        created_at=slot + timedelta(minutes=10),
        suffix="ok",
        run_id=123,
    )
    report = anchor_store.verify(batch_store=batch_store)
    assert report["status"] == "VERIFIED"
    assert report["anchor_count"] == 1
    assert record["anchor_created_at"] == (slot + timedelta(minutes=10)).isoformat()


def test_anchor_receipt_mismatch_and_non_main_run_fail_closed(tmp_path: Path) -> None:
    slot = datetime(2026, 9, 15, 0, tzinfo=UTC)
    batch_store = ProviderBatchStore(tmp_path / "batches")
    batch = _capture(
        tmp_path,
        batch_store,
        schedule_date=slot.date(),
        observed_at=slot + timedelta(minutes=5),
        summaries=[],
        name="batch.json",
    )

    bad_anchor_store = ProviderBatchAnchorStore(tmp_path / "anchors-bad-receipt")
    receipt, run = _anchor_evidence(
        tmp_path,
        batch,
        created_at=slot + timedelta(minutes=10),
        suffix="bad-receipt",
        run_id=124,
        receipt_overrides={"manifest_sha256": "0" * 64},
    )
    with pytest.raises(ValueError, match="manifest_sha256 mismatch"):
        attest_batch_anchor(
            store=bad_anchor_store,
            batch_store=batch_store,
            batch_record_sha256=str(batch["record_sha256"]),
            anchor_receipt_path=receipt,
            github_run_metadata_path=run,
        )

    branch_anchor_store = ProviderBatchAnchorStore(tmp_path / "anchors-bad-branch")
    receipt, run = _anchor_evidence(
        tmp_path,
        batch,
        created_at=slot + timedelta(minutes=10),
        suffix="bad-branch",
        run_id=125,
        head_branch="dev/test",
    )
    with pytest.raises(ValueError, match="must run from main"):
        attest_batch_anchor(
            store=branch_anchor_store,
            batch_store=batch_store,
            batch_record_sha256=str(batch["record_sha256"]),
            anchor_receipt_path=receipt,
            github_run_metadata_path=run,
        )


def test_anchor_more_than_one_hour_after_observation_is_rejected(tmp_path: Path) -> None:
    slot = datetime(2026, 9, 15, 0, tzinfo=UTC)
    observed = slot + timedelta(minutes=5)
    batch_store = ProviderBatchStore(tmp_path / "batches")
    anchor_store = ProviderBatchAnchorStore(tmp_path / "anchors")
    batch = _capture(
        tmp_path,
        batch_store,
        schedule_date=slot.date(),
        observed_at=observed,
        summaries=[],
        name="batch.json",
    )
    receipt, run = _anchor_evidence(
        tmp_path,
        batch,
        created_at=observed + timedelta(hours=1, seconds=1),
        suffix="late",
        run_id=126,
    )
    with pytest.raises(ValueError, match="more than one hour"):
        attest_batch_anchor(
            store=anchor_store,
            batch_store=batch_store,
            batch_record_sha256=str(batch["record_sha256"]),
            anchor_receipt_path=receipt,
            github_run_metadata_path=run,
        )


def test_cadence_requires_current_and_next_day_for_each_due_slot(tmp_path: Path) -> None:
    slot = datetime(2026, 9, 15, 0, tzinfo=UTC)
    batch_store = ProviderBatchStore(tmp_path / "batches")
    anchor_store = ProviderBatchAnchorStore(tmp_path / "anchors")
    _anchor_two_dates_for_slot(
        tmp_path,
        batch_store=batch_store,
        anchor_store=anchor_store,
        slot=slot,
    )
    report = verify_capture_cadence(
        batch_store=batch_store,
        anchor_store=anchor_store,
        coverage_start=slot,
        complete_through=slot + timedelta(hours=1),
    )
    assert report["status"] == "CADENCE_COMPLETE"
    assert report["due_slot_count"] == 1
    assert report["covered_slot_date_count"] == 2


def test_missing_next_day_or_later_slot_blocks_cadence(tmp_path: Path) -> None:
    slot = datetime(2026, 9, 15, 0, tzinfo=UTC)
    batch_store = ProviderBatchStore(tmp_path / "batches")
    anchor_store = ProviderBatchAnchorStore(tmp_path / "anchors")
    current = _capture(
        tmp_path,
        batch_store,
        schedule_date=slot.date(),
        observed_at=slot + timedelta(minutes=10),
        summaries=[],
        name="current.json",
    )
    _attest(
        tmp_path,
        anchor_store,
        batch_store,
        current,
        created_at=slot + timedelta(minutes=20),
        suffix="current",
        run_id=130,
    )
    with pytest.raises(ValueError, match="missing anchored slot/date coverage"):
        verify_capture_cadence(
            batch_store=batch_store,
            anchor_store=anchor_store,
            coverage_start=slot,
            complete_through=slot + timedelta(hours=1),
        )

    next_day = _capture(
        tmp_path,
        batch_store,
        schedule_date=slot.date() + timedelta(days=1),
        observed_at=slot + timedelta(minutes=25),
        summaries=[],
        name="next.json",
    )
    _attest(
        tmp_path,
        anchor_store,
        batch_store,
        next_day,
        created_at=slot + timedelta(minutes=35),
        suffix="next",
        run_id=131,
    )
    with pytest.raises(ValueError, match="2026-09-15T06:00:00"):
        verify_capture_cadence(
            batch_store=batch_store,
            anchor_store=anchor_store,
            coverage_start=slot,
            complete_through=slot + timedelta(hours=7),
        )


def test_anchored_reconciliation_requires_external_prestart_time(tmp_path: Path) -> None:
    slot = datetime(2026, 9, 15, 0, tzinfo=UTC)
    event_start = slot + timedelta(minutes=30)
    batch_store = ProviderBatchStore(tmp_path / "batches")
    anchor_store = ProviderBatchAnchorStore(tmp_path / "anchors")
    census_store = EventCensusStore(tmp_path / "census")

    current = _capture(
        tmp_path,
        batch_store,
        schedule_date=slot.date(),
        observed_at=slot + timedelta(minutes=10),
        summaries=[_summary("sr:sport_event:900", start=event_start)],
        name="current.json",
    )
    _attest(
        tmp_path,
        anchor_store,
        batch_store,
        current,
        created_at=slot + timedelta(minutes=20),
        suffix="current",
        run_id=140,
    )
    next_day = _capture(
        tmp_path,
        batch_store,
        schedule_date=slot.date() + timedelta(days=1),
        observed_at=slot + timedelta(minutes=25),
        summaries=[],
        name="next.json",
    )
    _attest(
        tmp_path,
        anchor_store,
        batch_store,
        next_day,
        created_at=slot + timedelta(minutes=35),
        suffix="next",
        run_id=141,
    )
    _record_census(
        tmp_path,
        census_store,
        event_id="sr:sport_event:900",
        observed_at=slot + timedelta(minutes=10),
        scheduled_start=event_start,
    )
    report = reconcile_anchored_batches_with_census(
        batch_store=batch_store,
        anchor_store=anchor_store,
        census_store=census_store,
        coverage_start=slot,
        complete_through=slot + timedelta(hours=1),
    )
    assert report["status"] == "ANCHORED_RECONCILED"
    assert report["required_event_count"] == 1


def test_poststart_anchor_cannot_make_locally_prestart_event_trusted(tmp_path: Path) -> None:
    slot = datetime(2026, 9, 15, 0, tzinfo=UTC)
    event_start = slot + timedelta(minutes=30)
    batch_store = ProviderBatchStore(tmp_path / "batches")
    anchor_store = ProviderBatchAnchorStore(tmp_path / "anchors")
    census_store = EventCensusStore(tmp_path / "census")

    current = _capture(
        tmp_path,
        batch_store,
        schedule_date=slot.date(),
        observed_at=slot + timedelta(minutes=10),
        summaries=[_summary("sr:sport_event:901", start=event_start)],
        name="current.json",
    )
    _attest(
        tmp_path,
        anchor_store,
        batch_store,
        current,
        created_at=slot + timedelta(minutes=40),
        suffix="current",
        run_id=150,
    )
    next_day = _capture(
        tmp_path,
        batch_store,
        schedule_date=slot.date() + timedelta(days=1),
        observed_at=slot + timedelta(minutes=20),
        summaries=[],
        name="next.json",
    )
    _attest(
        tmp_path,
        anchor_store,
        batch_store,
        next_day,
        created_at=slot + timedelta(minutes=25),
        suffix="next",
        run_id=151,
    )
    _record_census(
        tmp_path,
        census_store,
        event_id="sr:sport_event:901",
        observed_at=slot + timedelta(minutes=10),
        scheduled_start=event_start,
    )
    with pytest.raises(ValueError, match="lack an externally timestamped pre-start batch"):
        reconcile_anchored_batches_with_census(
            batch_store=batch_store,
            anchor_store=anchor_store,
            census_store=census_store,
            coverage_start=slot,
            complete_through=slot + timedelta(hours=1),
        )


def test_unanchored_extra_batch_cannot_rescue_denominator(tmp_path: Path) -> None:
    slot = datetime(2026, 9, 15, 0, tzinfo=UTC)
    event_start = slot + timedelta(minutes=45)
    batch_store = ProviderBatchStore(tmp_path / "batches")
    anchor_store = ProviderBatchAnchorStore(tmp_path / "anchors")
    census_store = EventCensusStore(tmp_path / "census")

    current = _capture(
        tmp_path,
        batch_store,
        schedule_date=slot.date(),
        observed_at=slot + timedelta(minutes=5),
        summaries=[],
        name="anchored-current.json",
    )
    _attest(
        tmp_path,
        anchor_store,
        batch_store,
        current,
        created_at=slot + timedelta(minutes=10),
        suffix="anchored-current",
        run_id=160,
    )
    next_day = _capture(
        tmp_path,
        batch_store,
        schedule_date=slot.date() + timedelta(days=1),
        observed_at=slot + timedelta(minutes=15),
        summaries=[],
        name="anchored-next.json",
    )
    _attest(
        tmp_path,
        anchor_store,
        batch_store,
        next_day,
        created_at=slot + timedelta(minutes=20),
        suffix="anchored-next",
        run_id=161,
    )
    _capture(
        tmp_path,
        batch_store,
        schedule_date=slot.date(),
        observed_at=slot + timedelta(minutes=25),
        summaries=[_summary("sr:sport_event:902", start=event_start)],
        name="unanchored-extra.json",
    )
    _record_census(
        tmp_path,
        census_store,
        event_id="sr:sport_event:902",
        observed_at=slot + timedelta(minutes=25),
        scheduled_start=event_start,
    )
    with pytest.raises(ValueError, match="lack an externally timestamped pre-start batch"):
        reconcile_anchored_batches_with_census(
            batch_store=batch_store,
            anchor_store=anchor_store,
            census_store=census_store,
            coverage_start=slot,
            complete_through=slot + timedelta(hours=1),
        )
