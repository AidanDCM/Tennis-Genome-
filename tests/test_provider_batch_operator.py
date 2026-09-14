from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tennis_genome.prospective.provider_batch import (
    ProviderBatchStore,
    capture_provider_batch,
)
from tennis_genome.prospective.provider_batch_operator import (
    ANCHOR_INPUT_FIELDS,
    ANCHOR_PACKET_SCHEMA,
    ANCHOR_WORKFLOW_PATH,
    build_anchor_dispatch_packet,
    capture_batch_and_build_anchor_packet,
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
                    "id": "sr:competition:operator-test",
                    "name": "Operator Test",
                    "type": "singles",
                },
            },
            "competitors": [],
        },
        "sport_event_status": {"status": "not_started"},
    }


def _payload(path: Path, *, event_id: str, start: datetime) -> Path:
    path.write_text(
        json.dumps({"summaries": [_summary(event_id, start=start)]}, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return path


def _packet_core(packet: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in packet.items() if key != "packet_sha256"}


def test_capture_emits_exact_workflow_dispatch_inputs(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    raw = _payload(
        tmp_path / "daily.json",
        event_id="sr:sport_event:operator-1",
        start=observed + timedelta(hours=4),
    )
    store = ProviderBatchStore(tmp_path / "store")

    record, packet = capture_batch_and_build_anchor_packet(
        store=store,
        raw_payload_path=raw,
        schedule_date=observed.date(),
        observed_at=observed,
    )

    assert packet["schema_version"] == ANCHOR_PACKET_SCHEMA
    assert packet["workflow_path"] == ANCHOR_WORKFLOW_PATH
    inputs = packet["inputs"]
    assert isinstance(inputs, dict)
    assert tuple(inputs) == ANCHOR_INPUT_FIELDS
    assert inputs == {
        "batch_record_sha256": record["record_sha256"],
        "batch_chain_head_sha256": record["record_sha256"],
        "schedule_date": "2026-09-15",
        "raw_payload_sha256": record["raw_payload_sha256"],
        "manifest_sha256": record["manifest_sha256"],
        "observed_at": "2026-09-15T12:00:00+00:00",
    }
    expected_packet_sha = hashlib.sha256(
        json.dumps(
            _packet_core(packet),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    assert packet["packet_sha256"] == expected_packet_sha
    assert store.verify()["status"] == "VERIFIED"


def test_packet_rebuild_is_deterministic_for_current_head(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    raw = _payload(
        tmp_path / "daily.json",
        event_id="sr:sport_event:operator-2",
        start=observed + timedelta(hours=4),
    )
    store = ProviderBatchStore(tmp_path / "store")
    record = capture_provider_batch(
        store=store,
        raw_payload_path=raw,
        schedule_date=observed.date(),
        observed_at=observed,
    )

    first = build_anchor_dispatch_packet(store=store)
    second = build_anchor_dispatch_packet(
        store=store,
        record_sha256=str(record["record_sha256"]),
    )

    assert first == second


def test_stale_record_cannot_generate_anchor_packet(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    store = ProviderBatchStore(tmp_path / "store")
    first_raw = _payload(
        tmp_path / "first.json",
        event_id="sr:sport_event:operator-3",
        start=observed + timedelta(hours=4),
    )
    first = capture_provider_batch(
        store=store,
        raw_payload_path=first_raw,
        schedule_date=observed.date(),
        observed_at=observed,
    )
    second_observed = observed + timedelta(hours=1)
    second_raw = _payload(
        tmp_path / "second.json",
        event_id="sr:sport_event:operator-4",
        start=second_observed + timedelta(hours=4),
    )
    capture_provider_batch(
        store=store,
        raw_payload_path=second_raw,
        schedule_date=second_observed.date(),
        observed_at=second_observed,
    )

    with pytest.raises(ValueError, match="current chain-head record"):
        build_anchor_dispatch_packet(
            store=store,
            record_sha256=str(first["record_sha256"]),
        )


def test_capture_refuses_schedule_date_different_from_observation_utc_date(
    tmp_path: Path,
) -> None:
    observed = datetime(2026, 9, 15, 23, 30, tzinfo=UTC)
    raw = _payload(
        tmp_path / "daily.json",
        event_id="sr:sport_event:operator-5",
        start=observed + timedelta(hours=2),
    )
    store = ProviderBatchStore(tmp_path / "store")

    with pytest.raises(ValueError, match="schedule_date must equal observed_at UTC date"):
        capture_batch_and_build_anchor_packet(
            store=store,
            raw_payload_path=raw,
            schedule_date=(observed + timedelta(days=1)).date(),
            observed_at=observed,
        )

    assert store.verify()["record_count"] == 0


def test_packet_refuses_existing_record_with_schedule_date_mismatch(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 23, 30, tzinfo=UTC)
    raw = _payload(
        tmp_path / "daily.json",
        event_id="sr:sport_event:operator-6",
        start=observed + timedelta(hours=2),
    )
    store = ProviderBatchStore(tmp_path / "store")
    capture_provider_batch(
        store=store,
        raw_payload_path=raw,
        schedule_date=(observed + timedelta(days=1)).date(),
        observed_at=observed,
    )

    with pytest.raises(ValueError, match="schedule date must equal observed_at UTC date"):
        build_anchor_dispatch_packet(store=store)


def test_empty_store_cannot_generate_anchor_packet(tmp_path: Path) -> None:
    store = ProviderBatchStore(tmp_path / "store")

    with pytest.raises(ValueError, match="no retained batch records"):
        build_anchor_dispatch_packet(store=store)
