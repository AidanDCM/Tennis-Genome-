from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tennis_genome.prospective.provider_batch import ProviderBatchStore
from tennis_genome.prospective.provider_batch_operator import (
    ANCHOR_INPUT_FIELDS,
    build_anchor_dispatch_packet,
    capture_pages_and_build_anchor_packet,
)


def _summary(event_id: str, *, start: datetime) -> dict[str, object]:
    return {
        "sport_event": {
            "id": event_id,
            "start_time": start.isoformat(),
            "sport_event_context": {
                "category": {"id": "sr:category:3", "name": "ATP"},
                "competition": {
                    "id": f"sr:competition:{event_id.rsplit(':', 1)[-1]}",
                    "name": "Operator Pagination Test",
                    "type": "singles",
                },
            },
        },
        "sport_event_status": {"status": "not_started"},
    }


def _page(
    tmp_path: Path,
    name: str,
    summaries: list[dict[str, object]],
    *,
    total: int,
    offset: int,
    generated_at: str = "2026-09-15T11:58:00+00:00",
) -> tuple[Path, Path]:
    raw = tmp_path / f"{name}.json"
    raw.write_text(
        json.dumps({"generated_at": generated_at, "summaries": summaries}) + "\n",
        encoding="utf-8",
    )
    headers = tmp_path / f"{name}.headers"
    headers.write_text(
        "HTTP/2 200\n"
        f"X-Max-Results: {total}\n"
        f"X-Offset: {offset}\n"
        f"X-Result: {len(summaries)}\n",
        encoding="utf-8",
    )
    return raw, headers


def test_paginated_capture_emits_anchor_packet_only_after_complete_verification(
    tmp_path: Path,
) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(hours=4)
    page0 = _page(
        tmp_path,
        "page0",
        [_summary("sr:sport_event:op-page-1", start=start)],
        total=2,
        offset=0,
        generated_at="2026-09-15T11:57:00+00:00",
    )
    page1 = _page(
        tmp_path,
        "page1",
        [_summary("sr:sport_event:op-page-2", start=start)],
        total=2,
        offset=1,
    )
    store = ProviderBatchStore(tmp_path / "store")

    record, packet = capture_pages_and_build_anchor_packet(
        store=store,
        raw_page_paths=[page0[0], page1[0]],
        header_page_paths=[page0[1], page1[1]],
        schedule_date=observed.date(),
        observed_at=observed,
    )

    inputs = packet["inputs"]
    assert isinstance(inputs, dict)
    assert tuple(inputs) == ANCHOR_INPUT_FIELDS
    assert inputs["batch_record_sha256"] == record["record_sha256"]
    assert inputs["batch_chain_head_sha256"] == record["record_sha256"]
    assert record["page_count"] == 2
    assert record["raw_summary_count"] == 2
    assert record["provider_generated_at_min"] == "2026-09-15T11:57:00+00:00"
    assert record["provider_generated_at_max"] == "2026-09-15T11:58:00+00:00"


def test_paginated_capture_requires_equal_raw_and_header_counts(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    store = ProviderBatchStore(tmp_path / "store")

    with pytest.raises(ValueError, match="counts must match"):
        capture_pages_and_build_anchor_packet(
            store=store,
            raw_page_paths=[tmp_path / "one.json"],
            header_page_paths=[],
            schedule_date=observed.date(),
            observed_at=observed,
        )


def test_operator_rejects_stale_provider_generation_time(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    page = _page(
        tmp_path,
        "stale",
        [_summary("sr:sport_event:op-stale", start=observed + timedelta(hours=4))],
        total=1,
        offset=0,
        generated_at="2026-09-15T11:49:00+00:00",
    )
    store = ProviderBatchStore(tmp_path / "store")

    with pytest.raises(ValueError, match="exceeds frozen 10-minute provider-generation lag"):
        capture_pages_and_build_anchor_packet(
            store=store,
            raw_page_paths=[page[0]],
            header_page_paths=[page[1]],
            schedule_date=observed.date(),
            observed_at=observed,
        )
    assert store.verify()["record_count"] == 0


def test_anchor_packet_rechecks_retained_paginated_evidence(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(hours=4)
    page = _page(
        tmp_path,
        "page0",
        [_summary("sr:sport_event:op-page-3", start=start)],
        total=1,
        offset=0,
    )
    store = ProviderBatchStore(tmp_path / "store")
    record, _ = capture_pages_and_build_anchor_packet(
        store=store,
        raw_page_paths=[page[0]],
        header_page_paths=[page[1]],
        schedule_date=observed.date(),
        observed_at=observed,
    )
    raw_page_sha = str(record["page_evidence"][0]["raw_payload_sha256"])
    (store.evidence_dir / raw_page_sha).write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="evidence digest mismatch"):
        build_anchor_dispatch_packet(store=store)
