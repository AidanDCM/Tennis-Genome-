from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tennis_genome.prospective.census import (
    CensusStatus,
    EventCensusStore,
    record_discovery,
    record_disposition,
)


def _discovery_path(tmp_path: Path) -> Path:
    path = tmp_path / "discovery.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "full-stack-forward-census-discovery-v1",
                "provider": "SPORTRADAR",
                "provider_event_id": "event-1",
                "tour": "ATP",
                "event_type": "singles",
                "observed_at": "2026-09-20T12:00:00+00:00",
                "scheduled_start": "2026-09-20T14:00:00+00:00",
                "match_id": "match-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _support_path(tmp_path: Path) -> Path:
    path = tmp_path / "support.json"
    path.write_text('{"source":"operator-log","retained":true}\n', encoding="utf-8")
    return path


def _input_unavailable_disposition(
    tmp_path: Path,
) -> tuple[EventCensusStore, dict[str, object]]:
    store = EventCensusStore(tmp_path / "census")
    discovery = record_discovery(
        store=store,
        discovery_evidence_path=_discovery_path(tmp_path),
    )
    disposition = record_disposition(
        store=store,
        discovery_record_sha256=str(discovery["record_sha256"]),
        status=CensusStatus.INPUT_UNAVAILABLE,
        reason_code="IDENTITY_UNRESOLVED",
        disposed_at=datetime(2026, 9, 20, 12, 30, tzinfo=UTC),
        supporting_evidence_paths=[_support_path(tmp_path)],
    )
    return store, disposition


def test_disposition_retains_canonical_evidence_digest_and_fields(tmp_path: Path) -> None:
    store, disposition = _input_unavailable_disposition(tmp_path)

    evidence_sha = str(disposition["disposition_evidence_sha256"])
    assert evidence_sha in disposition["evidence_sha256"]
    raw = json.loads((store.evidence_dir / evidence_sha).read_text(encoding="utf-8"))
    assert raw == {
        "schema_version": "full-stack-forward-census-disposition-v1",
        "event_key": "SPORTRADAR:event-1",
        "status": "INPUT_UNAVAILABLE",
        "reason_code": "IDENTITY_UNRESOLVED",
        "disposed_at": "2026-09-20T12:30:00+00:00",
        "prediction_record_sha256": None,
        "match_id": None,
    }
    assert store.verify()["status"] == "VERIFIED"


def test_verifier_rederives_disposition_fields_from_canonical_evidence(
    tmp_path: Path,
) -> None:
    store, _ = _input_unavailable_disposition(tmp_path)

    record_path = sorted(store.records_dir.glob("*.json"))[-1]
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["reason_code"] = "FOUNDATIONAL_STATE_UNAVAILABLE"
    unsigned = dict(record)
    unsigned.pop("record_sha256")
    digest = hashlib.sha256(
        json.dumps(
            unsigned,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    record["record_sha256"] = digest
    record_path.unlink()
    rewritten = store.records_dir / f"{int(record['sequence']):08d}-{digest}.json"
    rewritten.write_text(
        json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="reason_code does not reproduce from evidence"):
        store.verify()
