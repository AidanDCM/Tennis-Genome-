from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tennis_genome.prospective.census import (
    CensusStatus,
    EventCensusStore,
    reconcile_with_pilot,
    record_discovery,
    record_disposition,
)


def _write_discovery(
    tmp_path: Path,
    *,
    event_id: str = "event-1",
    tour: str = "ATP",
    observed_at: str = "2026-09-20T12:00:00+00:00",
    scheduled_start: str = "2026-09-20T14:00:00+00:00",
    match_id: str | None = "match-1",
) -> Path:
    payload = {
        "schema_version": "full-stack-forward-census-discovery-v1",
        "provider": "SPORTRADAR",
        "provider_event_id": event_id,
        "tour": tour,
        "event_type": "singles",
        "observed_at": observed_at,
        "scheduled_start": scheduled_start,
        "match_id": match_id,
    }
    path = tmp_path / f"discovery-{event_id}.json"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


def _supporting_evidence(tmp_path: Path, name: str = "support.json") -> Path:
    path = tmp_path / name
    path.write_text('{"source":"operator-log","retained":true}\n', encoding="utf-8")
    return path


class _FakePilotStore:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self._records = records

    def records(self) -> list[dict[str, object]]:
        return [dict(record) for record in self._records]

    def verify(self) -> dict[str, object]:
        return {
            "status": "VERIFIED",
            "prediction_count": sum(
                record.get("record_type") == "PREDICTION_COMMIT" for record in self._records
            ),
            "chain_head_sha256": "f" * 64,
        }


def _pilot_prediction(
    *,
    sha: str = "a" * 64,
    match_id: str = "match-1",
    tour: str = "ATP",
    scheduled_start: str = "2026-09-20T14:00:00+00:00",
    committed_at: str = "2026-09-20T13:00:00+00:00",
) -> dict[str, object]:
    return {
        "record_type": "PREDICTION_COMMIT",
        "record_sha256": sha,
        "match_id": match_id,
        "tour": tour,
        "scheduled_start": scheduled_start,
        "committed_at": committed_at,
    }


def test_discovery_is_hash_chained_and_open_until_disposed(tmp_path: Path) -> None:
    store = EventCensusStore(tmp_path / "census")
    discovery = record_discovery(
        store=store,
        discovery_evidence_path=_write_discovery(tmp_path),
    )

    report = store.verify()
    assert report["status"] == "VERIFIED"
    assert report["discovery_count"] == 1
    assert report["disposition_count"] == 0
    assert report["open_count"] == 1
    assert report["open_event_keys"] == ["SPORTRADAR:event-1"]
    assert discovery["previous_record_sha256"] == "0" * 64
    assert discovery["record_sha256"] == report["chain_head_sha256"]


def test_census_rejects_duplicate_discovery(tmp_path: Path) -> None:
    store = EventCensusStore(tmp_path / "census")
    evidence = _write_discovery(tmp_path)
    record_discovery(store=store, discovery_evidence_path=evidence)

    with pytest.raises(ValueError, match="already exists"):
        record_discovery(store=store, discovery_evidence_path=evidence)


def test_nonpredicted_disposition_requires_frozen_reason_and_evidence(tmp_path: Path) -> None:
    store = EventCensusStore(tmp_path / "census")
    discovery = record_discovery(
        store=store,
        discovery_evidence_path=_write_discovery(tmp_path),
    )

    with pytest.raises(ValueError, match="reason_code"):
        record_disposition(
            store=store,
            discovery_record_sha256=str(discovery["record_sha256"]),
            status=CensusStatus.INPUT_UNAVAILABLE,
            reason_code="OTHER",
            disposed_at=datetime(2026, 9, 20, 12, 30, tzinfo=UTC),
            supporting_evidence_paths=[_supporting_evidence(tmp_path)],
        )

    with pytest.raises(ValueError, match="requires supporting evidence"):
        record_disposition(
            store=store,
            discovery_record_sha256=str(discovery["record_sha256"]),
            status=CensusStatus.INPUT_UNAVAILABLE,
            reason_code="FOUNDATIONAL_STATE_UNAVAILABLE",
            disposed_at=datetime(2026, 9, 20, 12, 30, tzinfo=UTC),
        )


def test_nonpredicted_terminal_status_closes_denominator_with_reason(tmp_path: Path) -> None:
    store = EventCensusStore(tmp_path / "census")
    discovery = record_discovery(
        store=store,
        discovery_evidence_path=_write_discovery(tmp_path),
    )
    disposition = record_disposition(
        store=store,
        discovery_record_sha256=str(discovery["record_sha256"]),
        status=CensusStatus.INPUT_UNAVAILABLE,
        reason_code="IDENTITY_UNRESOLVED",
        disposed_at=datetime(2026, 9, 20, 12, 30, tzinfo=UTC),
        supporting_evidence_paths=[_supporting_evidence(tmp_path)],
    )

    report = store.verify()
    assert disposition["status"] == "INPUT_UNAVAILABLE"
    assert report["open_count"] == 0
    assert report["status_counts"] == {"INPUT_UNAVAILABLE": 1}
    assert report["reason_counts"] == {"IDENTITY_UNRESOLVED": 1}


def test_predicted_disposition_requires_prediction_binding(tmp_path: Path) -> None:
    store = EventCensusStore(tmp_path / "census")
    discovery = record_discovery(
        store=store,
        discovery_evidence_path=_write_discovery(tmp_path),
    )

    with pytest.raises(ValueError, match="prediction_record_sha256"):
        record_disposition(
            store=store,
            discovery_record_sha256=str(discovery["record_sha256"]),
            status=CensusStatus.PREDICTED,
            reason_code="PREDICTION_COMMITTED",
            disposed_at=datetime(2026, 9, 20, 13, 1, tzinfo=UTC),
            match_id="match-1",
        )


def test_successful_prediction_reconciliation_binds_census_to_pilot(tmp_path: Path) -> None:
    store = EventCensusStore(tmp_path / "census")
    discovery = record_discovery(
        store=store,
        discovery_evidence_path=_write_discovery(tmp_path),
    )
    prediction = _pilot_prediction()
    record_disposition(
        store=store,
        discovery_record_sha256=str(discovery["record_sha256"]),
        status=CensusStatus.PREDICTED,
        reason_code="PREDICTION_COMMITTED",
        disposed_at=datetime(2026, 9, 20, 13, 1, tzinfo=UTC),
        prediction_record_sha256=str(prediction["record_sha256"]),
        match_id=str(prediction["match_id"]),
    )

    report = reconcile_with_pilot(
        census_store=store,
        pilot_store=_FakePilotStore([prediction]),
        complete_through=datetime(2026, 9, 20, 14, 30, tzinfo=UTC),
    )
    assert report["status"] == "RECONCILED"
    assert report["prediction_count"] == 1
    assert report["linked_prediction_count"] == 1
    assert report["open_count"] == 0


def test_reconciliation_rejects_pilot_prediction_missing_from_census(tmp_path: Path) -> None:
    store = EventCensusStore(tmp_path / "census")
    prediction = _pilot_prediction()

    with pytest.raises(ValueError, match="missing PREDICTED census disposition"):
        reconcile_with_pilot(
            census_store=store,
            pilot_store=_FakePilotStore([prediction]),
        )


def test_reconciliation_rejects_census_prediction_without_pilot_record(tmp_path: Path) -> None:
    store = EventCensusStore(tmp_path / "census")
    discovery = record_discovery(
        store=store,
        discovery_evidence_path=_write_discovery(tmp_path),
    )
    record_disposition(
        store=store,
        discovery_record_sha256=str(discovery["record_sha256"]),
        status=CensusStatus.PREDICTED,
        reason_code="PREDICTION_COMMITTED",
        disposed_at=datetime(2026, 9, 20, 13, 1, tzinfo=UTC),
        prediction_record_sha256="b" * 64,
        match_id="match-1",
    )

    with pytest.raises(ValueError, match="no matching pilot prediction"):
        reconcile_with_pilot(
            census_store=store,
            pilot_store=_FakePilotStore([]),
        )


def test_reconciliation_rejects_tour_schedule_and_match_mismatch(tmp_path: Path) -> None:
    store = EventCensusStore(tmp_path / "census")
    discovery = record_discovery(
        store=store,
        discovery_evidence_path=_write_discovery(tmp_path),
    )
    record_disposition(
        store=store,
        discovery_record_sha256=str(discovery["record_sha256"]),
        status=CensusStatus.PREDICTED,
        reason_code="PREDICTION_COMMITTED",
        disposed_at=datetime(2026, 9, 20, 13, 1, tzinfo=UTC),
        prediction_record_sha256="c" * 64,
        match_id="match-1",
    )

    with pytest.raises(ValueError, match="tour mismatch"):
        reconcile_with_pilot(
            census_store=store,
            pilot_store=_FakePilotStore([_pilot_prediction(sha="c" * 64, tour="WTA")]),
        )

    with pytest.raises(ValueError, match="scheduled_start mismatch"):
        reconcile_with_pilot(
            census_store=store,
            pilot_store=_FakePilotStore(
                [
                    _pilot_prediction(
                        sha="c" * 64,
                        scheduled_start="2026-09-20T15:00:00+00:00",
                    )
                ]
            ),
        )

    with pytest.raises(ValueError, match="match_id mismatch"):
        reconcile_with_pilot(
            census_store=store,
            pilot_store=_FakePilotStore(
                [_pilot_prediction(sha="c" * 64, match_id="different-match")]
            ),
        )


def test_completeness_cutoff_rejects_past_due_open_event(tmp_path: Path) -> None:
    store = EventCensusStore(tmp_path / "census")
    record_discovery(
        store=store,
        discovery_evidence_path=_write_discovery(tmp_path),
    )

    with pytest.raises(ValueError, match="unresolved events"):
        reconcile_with_pilot(
            census_store=store,
            pilot_store=_FakePilotStore([]),
            complete_through=datetime(2026, 9, 20, 14, 0, tzinfo=UTC),
        )


def test_operational_failure_may_be_recorded_after_start_but_is_retained(tmp_path: Path) -> None:
    store = EventCensusStore(tmp_path / "census")
    discovery = record_discovery(
        store=store,
        discovery_evidence_path=_write_discovery(tmp_path),
    )
    disposition = record_disposition(
        store=store,
        discovery_record_sha256=str(discovery["record_sha256"]),
        status=CensusStatus.OPERATIONAL_FAILURE,
        reason_code="MISSED_COMMIT_WINDOW",
        disposed_at=datetime(2026, 9, 20, 14, 5, tzinfo=UTC),
        supporting_evidence_paths=[_supporting_evidence(tmp_path, "ops.json")],
    )

    assert disposition["status"] == "OPERATIONAL_FAILURE"
    assert store.verify()["open_count"] == 0


def test_record_tampering_breaks_census_verification(tmp_path: Path) -> None:
    store = EventCensusStore(tmp_path / "census")
    record_discovery(
        store=store,
        discovery_evidence_path=_write_discovery(tmp_path),
    )
    record_path = next(store.records_dir.glob("*.json"))
    raw = json.loads(record_path.read_text(encoding="utf-8"))
    raw["tour"] = "WTA"
    record_path.write_text(json.dumps(raw, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="record digest mismatch"):
        store.verify()
