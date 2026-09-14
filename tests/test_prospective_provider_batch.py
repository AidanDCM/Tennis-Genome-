from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from tennis_genome.prospective.census import EventCensusStore, record_discovery
from tennis_genome.prospective.provider_batch import (
    ProviderBatchStore,
    capture_provider_batch,
    reconcile_batches_with_census,
)


def _summary(
    event_id: str,
    *,
    start: datetime,
    category_id: str = "sr:category:3",
    category_name: str = "ATP",
    competition_type: str = "singles",
    status: str = "not_started",
) -> dict[str, object]:
    return {
        "sport_event": {
            "id": event_id,
            "start_time": start.isoformat(),
            "start_time_confirmed": True,
            "sport_event_context": {
                "category": {"id": category_id, "name": category_name},
                "competition": {
                    "id": f"sr:competition:{event_id.rsplit(':', 1)[-1]}",
                    "name": "Test Competition",
                    "type": competition_type,
                },
            },
            "competitors": [],
        },
        "sport_event_status": {"status": status},
    }


def _write_payload(path: Path, summaries: list[dict[str, object]]) -> Path:
    path.write_text(
        json.dumps({"summaries": summaries}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _capture(
    tmp_path: Path,
    summaries: list[dict[str, object]],
    *,
    observed_at: datetime,
    name: str = "batch.json",
) -> ProviderBatchStore:
    store = ProviderBatchStore(tmp_path / "batch-store")
    payload = _write_payload(tmp_path / name, summaries)
    capture_provider_batch(
        store=store,
        raw_payload_path=payload,
        schedule_date=observed_at.date(),
        observed_at=observed_at,
    )
    return store


def _record_census_event(
    tmp_path: Path,
    store: EventCensusStore,
    *,
    event_id: str,
    tour: str,
    observed_at: datetime,
    scheduled_start: datetime,
) -> None:
    evidence = tmp_path / f"discovery-{event_id.rsplit(':', 1)[-1]}.json"
    evidence.write_text(
        json.dumps(
            {
                "schema_version": "full-stack-forward-census-discovery-v1",
                "provider": "SPORTRADAR",
                "provider_event_id": event_id,
                "tour": tour,
                "event_type": "SINGLES",
                "observed_at": observed_at.isoformat(),
                "scheduled_start": scheduled_start.isoformat(),
                "match_id": None,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    record_discovery(store=store, discovery_evidence_path=evidence)


def test_main_tour_atp_and_wta_are_required_but_wta_125_and_doubles_are_not(
    tmp_path: Path,
) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(hours=4)
    store = _capture(
        tmp_path,
        [
            _summary("sr:sport_event:1", start=start),
            _summary(
                "sr:sport_event:2",
                start=start,
                category_id="sr:category:6",
                category_name="WTA",
            ),
            _summary(
                "sr:sport_event:3",
                start=start,
                category_id="sr:category:871",
                category_name="WTA 125K",
            ),
            _summary("sr:sport_event:4", start=start, competition_type="doubles"),
        ],
        observed_at=observed,
    )
    report = store.verify()
    assert report["classification_counts"] == {
        "CENSUS_REQUIRED": 2,
        "OUT_OF_SCOPE": 2,
    }


def test_required_batch_event_must_have_matching_census_discovery(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(hours=4)
    batch_store = _capture(
        tmp_path,
        [_summary("sr:sport_event:10", start=start)],
        observed_at=observed,
    )
    census_store = EventCensusStore(tmp_path / "census")
    with pytest.raises(ValueError, match="missing census discovery"):
        reconcile_batches_with_census(
            batch_store=batch_store,
            census_store=census_store,
            complete_through=start,
        )

    _record_census_event(
        tmp_path,
        census_store,
        event_id="sr:sport_event:10",
        tour="ATP",
        observed_at=observed,
        scheduled_start=start,
    )
    report = reconcile_batches_with_census(
        batch_store=batch_store,
        census_store=census_store,
        complete_through=start,
    )
    assert report["status"] == "RECONCILED"
    assert report["required_event_count"] == 1


def test_late_capture_of_in_scope_match_is_denominator_failure(tmp_path: Path) -> None:
    start = datetime(2026, 9, 15, 12, tzinfo=UTC)
    observed = start + timedelta(minutes=1)
    batch_store = _capture(
        tmp_path,
        [_summary("sr:sport_event:20", start=start, status="live")],
        observed_at=observed,
    )
    census_store = EventCensusStore(tmp_path / "census")
    with pytest.raises(ValueError, match="denominator failures"):
        reconcile_batches_with_census(
            batch_store=batch_store,
            census_store=census_store,
            complete_through=observed,
        )


def test_raw_batch_tampering_is_detected(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(hours=4)
    store = _capture(
        tmp_path,
        [_summary("sr:sport_event:30", start=start)],
        observed_at=observed,
    )
    record = store.records()[0]
    raw_sha = str(record["raw_payload_sha256"])
    (store.evidence_dir / raw_sha).write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="evidence digest mismatch"):
        store.verify()


def test_future_required_event_is_not_due_before_completeness_cutoff(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(days=2)
    batch_store = _capture(
        tmp_path,
        [_summary("sr:sport_event:40", start=start)],
        observed_at=observed,
    )
    census_store = EventCensusStore(tmp_path / "census")
    report = reconcile_batches_with_census(
        batch_store=batch_store,
        census_store=census_store,
        complete_through=observed + timedelta(hours=1),
    )
    assert report["status"] == "RECONCILED"
    assert report["required_event_count"] == 0


def test_sportradar_census_discovery_cannot_exist_outside_retained_batches(
    tmp_path: Path,
) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    batch_store = _capture(tmp_path, [], observed_at=observed)
    census_store = EventCensusStore(tmp_path / "census")
    _record_census_event(
        tmp_path,
        census_store,
        event_id="sr:sport_event:50",
        tour="ATP",
        observed_at=observed,
        scheduled_start=observed + timedelta(hours=4),
    )
    with pytest.raises(ValueError, match="not supported by due provider batches"):
        reconcile_batches_with_census(
            batch_store=batch_store,
            census_store=census_store,
            complete_through=observed + timedelta(hours=5),
        )


def test_category_id_name_semantic_drift_fails_closed(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(hours=4)
    payload = _write_payload(
        tmp_path / "drift.json",
        [
            _summary(
                "sr:sport_event:60",
                start=start,
                category_id="sr:category:6",
                category_name="Different Tour",
            )
        ],
    )
    store = ProviderBatchStore(tmp_path / "batch-store")
    with pytest.raises(ValueError, match="semantic drift"):
        capture_provider_batch(
            store=store,
            raw_payload_path=payload,
            schedule_date=date(2026, 9, 15),
            observed_at=observed,
        )


def test_valid_prestart_capture_is_not_poisoned_by_later_live_recapture(
    tmp_path: Path,
) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(hours=1)
    batch_store = _capture(
        tmp_path,
        [_summary("sr:sport_event:70", start=start)],
        observed_at=observed,
        name="prestart.json",
    )
    late_payload = _write_payload(
        tmp_path / "live.json",
        [_summary("sr:sport_event:70", start=start, status="live")],
    )
    capture_provider_batch(
        store=batch_store,
        raw_payload_path=late_payload,
        schedule_date=start.date(),
        observed_at=start + timedelta(minutes=5),
    )
    census_store = EventCensusStore(tmp_path / "census")
    _record_census_event(
        tmp_path,
        census_store,
        event_id="sr:sport_event:70",
        tour="ATP",
        observed_at=observed,
        scheduled_start=start,
    )
    report = reconcile_batches_with_census(
        batch_store=batch_store,
        census_store=census_store,
        complete_through=start + timedelta(minutes=10),
    )
    assert report["status"] == "RECONCILED"
    assert report["required_event_count"] == 1


def test_out_of_scope_wta_125_event_cannot_be_promoted_into_census(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(hours=4)
    batch_store = _capture(
        tmp_path,
        [
            _summary(
                "sr:sport_event:80",
                start=start,
                category_id="sr:category:871",
                category_name="WTA 125K",
            )
        ],
        observed_at=observed,
    )
    census_store = EventCensusStore(tmp_path / "census")
    _record_census_event(
        tmp_path,
        census_store,
        event_id="sr:sport_event:80",
        tour="WTA",
        observed_at=observed,
        scheduled_start=start,
    )
    with pytest.raises(ValueError, match="NOT_CENSUS_REQUIRED"):
        reconcile_batches_with_census(
            batch_store=batch_store,
            census_store=census_store,
            complete_through=start,
        )
