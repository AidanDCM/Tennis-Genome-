from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from tennis_genome.prospective.provider_batch import ProviderBatchStore
from tennis_genome.prospective.provider_batch_pagination import (
    build_complete_daily_payload,
    capture_paginated_provider_batch,
    verify_paginated_provider_batches,
)

_DEFAULT_GENERATED_AT = "2026-09-15T11:58:00+00:00"


def _summary(event_id: str, *, start: datetime) -> dict[str, object]:
    return {
        "sport_event": {
            "id": event_id,
            "start_time": start.isoformat(),
            "sport_event_context": {
                "category": {"id": "sr:category:3", "name": "ATP"},
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
    *,
    offset: int,
    total: int,
    summaries: list[dict[str, object]],
    name_offset: int | None = None,
    generated_at: str = _DEFAULT_GENERATED_AT,
) -> tuple[Path, Path]:
    file_offset = offset if name_offset is None else name_offset
    raw = tmp_path / f"page-{file_offset}.json"
    headers = tmp_path / f"page-{file_offset}.headers.txt"
    raw.write_text(
        json.dumps(
            {"generated_at": generated_at, "summaries": summaries},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    headers.write_text(
        "HTTP/2 200\n"
        f"X-Max-Results: {total}\n"
        f"X-Offset: {offset}\n"
        f"X-Result: {len(summaries)}\n",
        encoding="iso-8859-1",
    )
    return raw, headers


def test_two_page_capture_proves_complete_denominator_and_retains_page_evidence(
    tmp_path: Path,
) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(hours=4)
    first = _page(
        tmp_path,
        offset=0,
        total=3,
        summaries=[
            _summary("sr:sport_event:1", start=start),
            _summary("sr:sport_event:2", start=start),
        ],
        generated_at="2026-09-15T11:57:00+00:00",
    )
    second = _page(
        tmp_path,
        offset=2,
        total=3,
        summaries=[_summary("sr:sport_event:3", start=start)],
        generated_at="2026-09-15T11:58:00+00:00",
    )
    store = ProviderBatchStore(tmp_path / "store")
    record = capture_paginated_provider_batch(
        store=store,
        page_pairs=[second, first],
        schedule_date=date(2026, 9, 15),
        observed_at=observed,
    )

    assert record["raw_summary_count"] == 3
    assert record["page_count"] == 2
    assert record["provider_generated_at_min"] == "2026-09-15T11:57:00+00:00"
    assert record["provider_generated_at_max"] == "2026-09-15T11:58:00+00:00"
    report = verify_paginated_provider_batches(store)
    assert report["paginated_record_count"] == 1
    assert report["legacy_record_count"] == 0
    assert report["status"] == "VERIFIED"

    aggregate = json.loads(
        (store.evidence_dir / str(record["raw_payload_sha256"])).read_text(
            encoding="utf-8"
        )
    )
    assert aggregate["x_max_results"] == 3
    assert aggregate["provider_generated_at_spread_seconds"] == 60
    assert [page["offset"] for page in aggregate["pages"]] == [0, 2]
    for page in aggregate["pages"]:
        assert page["provider_generated_at"]
        assert (store.evidence_dir / page["raw_payload_sha256"]).is_file()
        assert (store.evidence_dir / page["response_headers_sha256"]).is_file()


def test_missing_second_page_fails_closed(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    page = _page(
        tmp_path,
        offset=0,
        total=3,
        summaries=[
            _summary("sr:sport_event:10", start=observed + timedelta(hours=2)),
            _summary("sr:sport_event:11", start=observed + timedelta(hours=3)),
        ],
    )
    with pytest.raises(ValueError, match="do not cover X-Max-Results exactly"):
        build_complete_daily_payload([page])


def test_gap_or_overlap_fails_closed(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    first = _page(
        tmp_path,
        offset=0,
        total=3,
        summaries=[_summary("sr:sport_event:20", start=observed + timedelta(hours=2))],
    )
    second = _page(
        tmp_path,
        offset=2,
        total=3,
        summaries=[_summary("sr:sport_event:21", start=observed + timedelta(hours=3))],
    )
    with pytest.raises(ValueError, match="gap or overlap"):
        build_complete_daily_payload([first, second])


def test_pages_must_agree_on_total(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    first = _page(
        tmp_path,
        offset=0,
        total=2,
        summaries=[_summary("sr:sport_event:30", start=observed + timedelta(hours=2))],
    )
    second = _page(
        tmp_path,
        offset=1,
        total=3,
        summaries=[_summary("sr:sport_event:31", start=observed + timedelta(hours=3))],
    )
    with pytest.raises(ValueError, match="disagree on X-Max-Results"):
        build_complete_daily_payload([first, second])


def test_x_result_must_match_page_body(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    raw, headers = _page(
        tmp_path,
        offset=0,
        total=1,
        summaries=[_summary("sr:sport_event:40", start=observed + timedelta(hours=2))],
    )
    headers.write_text(
        "HTTP/2 200\nX-Max-Results: 1\nX-Offset: 0\nX-Result: 0\n",
        encoding="iso-8859-1",
    )
    with pytest.raises(ValueError, match="summary count differs from X-Result"):
        build_complete_daily_payload([(raw, headers)])


def test_duplicate_event_across_pages_fails_closed(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    start = observed + timedelta(hours=2)
    first = _page(
        tmp_path,
        offset=0,
        total=2,
        summaries=[_summary("sr:sport_event:50", start=start)],
    )
    second = _page(
        tmp_path,
        offset=1,
        total=2,
        summaries=[_summary("sr:sport_event:50", start=start)],
    )
    with pytest.raises(ValueError, match="duplicate sport-event IDs"):
        build_complete_daily_payload([first, second])


def test_tampered_retained_page_is_detected(tmp_path: Path) -> None:
    observed = datetime(2026, 9, 15, 12, tzinfo=UTC)
    page = _page(
        tmp_path,
        offset=0,
        total=1,
        summaries=[_summary("sr:sport_event:60", start=observed + timedelta(hours=2))],
    )
    store = ProviderBatchStore(tmp_path / "store")
    record = capture_paginated_provider_batch(
        store=store,
        page_pairs=[page],
        schedule_date=observed.date(),
        observed_at=observed,
    )
    aggregate = json.loads(
        (store.evidence_dir / str(record["raw_payload_sha256"])).read_text(
            encoding="utf-8"
        )
    )
    raw_page_sha = aggregate["pages"][0]["raw_payload_sha256"]
    (store.evidence_dir / raw_page_sha).write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="evidence digest mismatch"):
        verify_paginated_provider_batches(store)


def test_zero_result_day_is_valid_as_exactly_one_empty_page(tmp_path: Path) -> None:
    page = _page(tmp_path, offset=0, total=0, summaries=[])
    payload = build_complete_daily_payload([page])
    assert payload["x_max_results"] == 0
    assert payload["page_count"] == 1
    assert payload["provider_generated_at_min"] == _DEFAULT_GENERATED_AT
    assert payload["summaries"] == []


def test_zero_result_day_rejects_extra_page(tmp_path: Path) -> None:
    first = _page(tmp_path, offset=0, total=0, summaries=[])
    second = _page(tmp_path, offset=0, total=0, summaries=[], name_offset=1)
    with pytest.raises(ValueError):
        build_complete_daily_payload([first, second])
