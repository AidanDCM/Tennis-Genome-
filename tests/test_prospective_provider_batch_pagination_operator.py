from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tennis_genome.prospective.provider_batch import ProviderBatchStore
from tennis_genome.prospective.provider_batch_pagination_operator import (
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
                    "id": "sr:competition:test",
                    "name": "Test",
                    "type": "singles",
                },
            },
        },
        "sport_event_status": {"status": "not_started"},
    }


def _page(
    tmp_path: Path,
    *,
    offset: int,
    total: int,
    summaries: list[dict[str, object]],
    generated_at: str = "2026-09-15T11:58:00+00:00",
):
    raw = tmp_path / f"page-{offset}.json"
    headers = tmp_path / f"page-{offset}.headers.txt"
    raw.write_text(
        json.dumps({"generated_at": generated_at, "summaries": summaries}) + "\n",
        encoding="utf-8",
    )
    headers.write_text(
        f"X-Max-Results: {total}\nX-Offset: {offset}\nX-Result: {len(summaries)}\n",
        encoding="iso-8859-1",
    )
    return raw, headers


def test_operator_emits_exact_six_field_anchor_packet_after_complete_pages(
    tmp_path: Path,
) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(hours=3)
    first = _page(
        tmp_path,
        offset=0,
        total=2,
        summaries=[_summary("sr:sport_event:1", start=start)],
        generated_at="2026-09-15T11:57:00+00:00",
    )
    second = _page(
        tmp_path,
        offset=1,
        total=2,
        summaries=[_summary("sr:sport_event:2", start=start)],
    )
    result = capture_pages_and_build_anchor_packet(
        store=ProviderBatchStore(tmp_path / "store"),
        page_pairs=[second, first],
        schedule_date=observed.date(),
        observed_at=observed,
    )

    assert result["pagination"]["status"] == "VERIFIED"
    inputs = result["anchor_packet"]["inputs"]
    assert tuple(inputs) == (
        "batch_record_sha256",
        "batch_chain_head_sha256",
        "schedule_date",
        "raw_payload_sha256",
        "manifest_sha256",
        "observed_at",
    )
    assert inputs["batch_record_sha256"] == inputs["batch_chain_head_sha256"]
    assert inputs["schedule_date"] == "2026-09-15"
