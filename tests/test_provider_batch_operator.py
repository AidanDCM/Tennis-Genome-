from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tennis_genome.prospective.provider_batch import (
    ProviderBatchStore,
    capture_provider_batch,
)
from tennis_genome.prospective.provider_batch_operator import (
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


def test_legacy_single_response_capture_fails_before_writing_anchorable_evidence(
    tmp_path: Path,
) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    raw = _payload(
        tmp_path / "daily.json",
        event_id="sr:sport_event:operator-1",
        start=observed + timedelta(hours=4),
    )
    store = ProviderBatchStore(tmp_path / "store")

    with pytest.raises(ValueError, match="legacy single-response capture cannot produce"):
        capture_batch_and_build_anchor_packet(
            store=store,
            raw_payload_path=raw,
            schedule_date=observed.date(),
            observed_at=observed,
        )

    assert store.verify()["record_count"] == 0


def test_legacy_current_head_cannot_generate_prospective_anchor_packet(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    raw = _payload(
        tmp_path / "daily.json",
        event_id="sr:sport_event:operator-2",
        start=observed + timedelta(hours=4),
    )
    store = ProviderBatchStore(tmp_path / "store")
    capture_provider_batch(
        store=store,
        raw_payload_path=raw,
        schedule_date=observed.date(),
        observed_at=observed,
    )

    with pytest.raises(ValueError, match="requires complete Sportradar pagination-v2 evidence"):
        build_anchor_dispatch_packet(store=store)


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


def test_empty_store_cannot_generate_anchor_packet(tmp_path: Path) -> None:
    store = ProviderBatchStore(tmp_path / "store")

    with pytest.raises(ValueError, match="no retained batch records"):
        build_anchor_dispatch_packet(store=store)
