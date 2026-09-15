from __future__ import annotations

import hashlib
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

_DEFAULT_GENERATED_AT = "2026-09-15T11:58:00+00:00"


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
    generated_at: str | None = _DEFAULT_GENERATED_AT,
) -> tuple[Path, Path]:
    raw = tmp_path / f"{name}.json"
    payload: dict[str, object] = {"summaries": summaries}
    if generated_at is not None:
        payload["generated_at"] = generated_at
    raw.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
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


def _canonical_sha(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


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
        generated_at="2026-09-15T11:57:00+00:00",
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
        generated_at="2026-09-15T11:58:00+00:00",
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
    assert record["provider_generated_at_min"] == "2026-09-15T11:57:00+00:00"
    assert record["provider_generated_at_max"] == "2026-09-15T11:58:00+00:00"
    assert record["provider_generated_at_spread_seconds"] == 60
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


def test_missing_provider_generated_at_is_rejected(tmp_path: Path) -> None:
    raw, headers = _page(
        tmp_path,
        "missing-generated",
        [],
        max_results=0,
        offset=0,
        generated_at=None,
    )
    with pytest.raises(ValueError, match="generated_at must be ISO-8601"):
        build_complete_daily_payload([(raw, headers)])


def test_naive_provider_generated_at_is_rejected(tmp_path: Path) -> None:
    page = _page(
        tmp_path,
        "naive-generated",
        [],
        max_results=0,
        offset=0,
        generated_at="2026-09-15T11:58:00",
    )
    with pytest.raises(ValueError, match="generated_at must be timezone-aware"):
        build_complete_daily_payload([page])


def test_provider_generation_spread_over_ten_minutes_is_rejected(tmp_path: Path) -> None:
    start = datetime(2026, 9, 15, 16, tzinfo=UTC)
    first = _page(
        tmp_path,
        "spread-first",
        [_summary("sr:sport_event:spread-1", start=start)],
        max_results=2,
        offset=0,
        generated_at="2026-09-15T11:40:00+00:00",
    )
    second = _page(
        tmp_path,
        "spread-second",
        [_summary("sr:sport_event:spread-2", start=start)],
        max_results=2,
        offset=1,
        generated_at="2026-09-15T11:51:00+00:00",
    )
    with pytest.raises(ValueError, match="spread exceeds frozen 10-minute"):
        build_complete_daily_payload([first, second])


def test_provider_pages_cannot_cross_utc_generation_date(tmp_path: Path) -> None:
    start = datetime(2026, 9, 16, 4, tzinfo=UTC)
    first = _page(
        tmp_path,
        "date-first",
        [_summary("sr:sport_event:date-1", start=start)],
        max_results=2,
        offset=0,
        generated_at="2026-09-15T23:59:00+00:00",
    )
    second = _page(
        tmp_path,
        "date-second",
        [_summary("sr:sport_event:date-2", start=start)],
        max_results=2,
        offset=1,
        generated_at="2026-09-16T00:01:00+00:00",
    )
    with pytest.raises(ValueError, match="cross a UTC provider-generation date boundary"):
        build_complete_daily_payload([first, second])


def test_observed_at_cannot_precede_provider_generation(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 11, 57, tzinfo=UTC)
    page = _page(
        tmp_path,
        "future-provider",
        [_summary("sr:sport_event:future-provider", start=observed + timedelta(hours=4))],
        max_results=1,
        offset=0,
        generated_at="2026-09-15T11:58:00+00:00",
    )
    store = ProviderBatchStore(tmp_path / "store")
    with pytest.raises(ValueError, match="observed_at cannot predate provider generated_at"):
        capture_paginated_provider_batch(
            store=store,
            page_pairs=[page],
            schedule_date=observed.date(),
            observed_at=observed,
        )
    assert store.verify()["record_count"] == 0


def test_observed_at_cannot_be_more_than_ten_minutes_after_provider_generation(
    tmp_path: Path,
) -> None:
    observed = datetime(2026, 9, 15, 12, 9, tzinfo=UTC)
    page = _page(
        tmp_path,
        "stale-provider",
        [_summary("sr:sport_event:stale-provider", start=observed + timedelta(hours=4))],
        max_results=1,
        offset=0,
        generated_at="2026-09-15T11:58:00+00:00",
    )
    store = ProviderBatchStore(tmp_path / "store")
    with pytest.raises(ValueError, match="exceeds frozen 10-minute provider-generation lag"):
        capture_paginated_provider_batch(
            store=store,
            page_pairs=[page],
            schedule_date=observed.date(),
            observed_at=observed,
        )
    assert store.verify()["record_count"] == 0


def test_schedule_date_must_equal_provider_generation_utc_date(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    page = _page(
        tmp_path,
        "wrong-date",
        [_summary("sr:sport_event:wrong-date", start=observed + timedelta(hours=4))],
        max_results=1,
        offset=0,
    )
    store = ProviderBatchStore(tmp_path / "store")
    with pytest.raises(ValueError, match="schedule_date must equal provider generated_at UTC date"):
        capture_paginated_provider_batch(
            store=store,
            page_pairs=[page],
            schedule_date=(observed + timedelta(days=1)).date(),
            observed_at=observed + timedelta(days=1),
        )


def test_coherently_tampered_record_provider_time_is_rejected_on_reload(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    page = _page(
        tmp_path,
        "tamper-time",
        [_summary("sr:sport_event:tamper-time", start=observed + timedelta(hours=4))],
        max_results=1,
        offset=0,
    )
    store = ProviderBatchStore(tmp_path / "store")
    capture_paginated_provider_batch(
        store=store,
        page_pairs=[page],
        schedule_date=observed.date(),
        observed_at=observed,
    )
    old_path = next(store.records_dir.glob("*.json"))
    record = json.loads(old_path.read_text(encoding="utf-8"))
    record["provider_generated_at_max"] = "2026-09-15T11:59:00+00:00"
    unsigned = dict(record)
    unsigned.pop("record_sha256")
    new_sha = _canonical_sha(unsigned)
    record["record_sha256"] = new_sha
    new_path = store.records_dir / f"00000001-{new_sha}.json"
    new_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    old_path.unlink()

    assert store.verify()["status"] == "VERIFIED"
    with pytest.raises(ValueError, match="max generated_at does not reproduce"):
        verify_paginated_provider_batches(store)


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
    assert payload["provider_generated_at_min"] == _DEFAULT_GENERATED_AT
    assert payload["provider_generated_at_max"] == _DEFAULT_GENERATED_AT
    assert payload["summaries"] == []
