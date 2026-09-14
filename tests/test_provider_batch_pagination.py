from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tennis_genome.prospective.provider_batch import ProviderBatchStore
from tennis_genome.prospective.provider_batch_pagination import (
    PAGINATION_SCHEMA,
    build_complete_daily_payload,
    capture_paginated_provider_batch,
    verify_paginated_provider_batches,
)


def _summary(
    event_id: str,
    *,
    start: datetime,
    category_id: str = "sr:category:3",
    category_name: str = "ATP",
) -> dict[str, object]:
    return {
        "sport_event": {
            "id": event_id,
            "start_time": start.isoformat(),
            "sport_event_context": {
                "category": {"id": category_id, "name": category_name},
                "competition": {
                    "id": f"sr:competition:{event_id.rsplit(':', 1)[-1]}",
                    "name": "Test Competition",
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
    max_results: int,
    offset: int,
    result_count: int | None = None,
) -> tuple[Path, Path]:
    raw = tmp_path / f"{name}.json"
    raw.write_text(
        json.dumps({"summaries": summaries}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    headers = tmp_path / f"{name}.headers"
    count = len(summaries) if result_count is None else result_count
    headers.write_text(
        "HTTP/2 200\n"
        f"X-Max-Results: {max_results}\n"
        f"X-Offset: {offset}\n"
        f"X-Result: {count}\n"
        "Content-Type: application/json\n",
        encoding="utf-8",
    )
    return raw, headers


def test_complete_two_page_capture_is_reproducible(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(hours=4)
    page0 = _page(
        tmp_path,
        "page0",
        [
            _summary("sr:sport_event:1", start=start),
            _summary("sr:sport_event:2", start=start),
        ],
        max_results=3,
        offset=0,
    )
    page2 = _page(
        tmp_path,
        "page2",
        [
            _summary(
                "sr:sport_event:3",
                start=start,
                category_id="sr:category:6",
                category_name="WTA",
            )
        ],
        max_results=3,
        offset=2,
    )
    store = ProviderBatchStore(tmp_path / "store")

    record = capture_paginated_provider_batch(
        store=store,
        page_pairs=[page2, page0],
        schedule_date=observed.date(),
        observed_at=observed,
    )

    assert record["pagination_schema"] == PAGINATION_SCHEMA
    assert record["page_count"] == 2
    assert record["raw_summary_count"] == 3
    assert len(record["page_evidence"]) == 2
    report = verify_paginated_provider_batches(store)
    assert report["paginated_record_count"] == 1
    assert report["legacy_record_count"] == 0
    assert report["status"] == "VERIFIED"


def test_pagination_gap_or_overlap_is_rejected(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(hours=4)
    page0 = _page(
        tmp_path,
        "page0",
        [_summary("sr:sport_event:10", start=start)],
        max_results=2,
        offset=0,
    )
    page2 = _page(
        tmp_path,
        "page2",
        [_summary("sr:sport_event:11", start=start)],
        max_results=2,
        offset=2,
    )
    with pytest.raises(ValueError, match="gap or overlap"):
        build_complete_daily_payload([page0, page2])


def test_pages_must_agree_on_total_results(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(hours=4)
    page0 = _page(
        tmp_path,
        "page0",
        [_summary("sr:sport_event:20", start=start)],
        max_results=2,
        offset=0,
    )
    page1 = _page(
        tmp_path,
        "page1",
        [_summary("sr:sport_event:21", start=start)],
        max_results=3,
        offset=1,
    )
    with pytest.raises(ValueError, match="disagree on X-Max-Results"):
        build_complete_daily_payload([page0, page1])


def test_x_result_must_equal_json_summary_count(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(hours=4)
    page = _page(
        tmp_path,
        "page0",
        [_summary("sr:sport_event:30", start=start)],
        max_results=2,
        offset=0,
        result_count=2,
    )
    with pytest.raises(ValueError, match="summary count differs from X-Result"):
        build_complete_daily_payload([page])


def test_duplicate_event_across_pages_is_rejected(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(hours=4)
    first = _page(
        tmp_path,
        "page0",
        [_summary("sr:sport_event:40", start=start)],
        max_results=2,
        offset=0,
    )
    second = _page(
        tmp_path,
        "page1",
        [_summary("sr:sport_event:40", start=start)],
        max_results=2,
        offset=1,
    )
    with pytest.raises(ValueError, match="duplicate sport-event IDs"):
        build_complete_daily_payload([first, second])


def test_missing_pagination_header_is_rejected(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(hours=4)
    raw, headers = _page(
        tmp_path,
        "page0",
        [_summary("sr:sport_event:50", start=start)],
        max_results=1,
        offset=0,
    )
    headers.write_text("HTTP/2 200\nX-Max-Results: 1\nX-Result: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required pagination fields"):
        build_complete_daily_payload([(raw, headers)])


def test_tampered_retained_page_is_detected(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(hours=4)
    page = _page(
        tmp_path,
        "page0",
        [_summary("sr:sport_event:60", start=start)],
        max_results=1,
        offset=0,
    )
    store = ProviderBatchStore(tmp_path / "store")
    record = capture_paginated_provider_batch(
        store=store,
        page_pairs=[page],
        schedule_date=observed.date(),
        observed_at=observed,
    )
    raw_page_sha = str(record["page_evidence"][0]["raw_payload_sha256"])
    (store.evidence_dir / raw_page_sha).write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="evidence digest mismatch"):
        verify_paginated_provider_batches(store)


def test_zero_result_capture_is_explicit_and_complete(tmp_path: Path) -> None:
    page = _page(
        tmp_path,
        "empty",
        [],
        max_results=0,
        offset=0,
    )
    payload = build_complete_daily_payload([page])
    assert payload["x_max_results"] == 0
    assert payload["page_count"] == 1
    assert payload["summaries"] == []
