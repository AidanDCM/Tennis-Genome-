from __future__ import annotations

import json
from pathlib import Path

import pytest

from tennis_genome.research_workbench.sportradar_start_time_audit import (
    audit_sportradar_start_time_coverage,
    build_complete_season_summaries,
)


def _summary(
    event_id: str,
    *,
    category_id: str = "sr:category:3",
    category_name: str = "ATP",
    competition_type: str = "singles",
    status: str = "closed",
    winning_reason: str | None = None,
) -> dict[str, object]:
    status_payload: dict[str, object] = {"status": status}
    if winning_reason is not None:
        status_payload["winning_reason"] = winning_reason
    return {
        "sport_event": {
            "id": event_id,
            "start_time": "2026-09-10T14:00:00Z",
            "start_time_confirmed": True,
            "estimated": False,
            "sport_event_context": {
                "category": {"id": category_id, "name": category_name},
                "competition": {
                    "id": "sr:competition:1",
                    "name": "Test Open",
                    "type": competition_type,
                },
            },
        },
        "sport_event_status": status_payload,
    }


def _timeline(
    event_id: str,
    *,
    starts: tuple[str, ...] = ("2026-09-10T14:03:04Z",),
    updated: bool = False,
    updated_time: str | None = None,
) -> dict[str, object]:
    timeline: list[dict[str, object]] = []
    for start in starts:
        event: dict[str, object] = {"type": "match_started", "time": start}
        if updated:
            event["updated"] = True
        if updated_time is not None:
            event["updated_time"] = updated_time
        timeline.append(event)
    return {"sport_event": {"id": event_id}, "timeline": timeline}


def _write_page(
    root: Path,
    *,
    name: str,
    offset: int,
    total: int,
    summaries: list[dict[str, object]],
    x_result: int | None = None,
) -> tuple[Path, Path]:
    raw = root / f"{name}.json"
    headers = root / f"{name}.headers.txt"
    raw.write_text(json.dumps({"summaries": summaries}), encoding="utf-8")
    count = len(summaries) if x_result is None else x_result
    headers.write_text(
        f"X-Max-Results: {total}\nX-Offset: {offset}\nX-Result: {count}\n",
        encoding="utf-8",
    )
    return raw, headers


def _write_timeline(root: Path, event_id: str, payload: dict[str, object]) -> Path:
    path = root / f"{event_id.rsplit(':', 1)[-1]}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_complete_two_page_season_summaries_is_deterministic(tmp_path: Path) -> None:
    first = _write_page(
        tmp_path,
        name="page-0",
        offset=0,
        total=3,
        summaries=[_summary("sr:sport_event:1"), _summary("sr:sport_event:2")],
    )
    second = _write_page(
        tmp_path,
        name="page-2",
        offset=2,
        total=3,
        summaries=[_summary("sr:sport_event:3")],
    )

    forward = build_complete_season_summaries((first, second))
    reversed_input = build_complete_season_summaries((second, first))

    assert forward == reversed_input
    assert forward["x_max_results"] == 3
    assert [row["sport_event"]["id"] for row in forward["summaries"]] == [
        "sr:sport_event:1",
        "sr:sport_event:2",
        "sr:sport_event:3",
    ]


@pytest.mark.parametrize(
    ("second_offset", "second_total"),
    ((3, 3), (1, 3), (2, 4)),
)
def test_season_pagination_rejects_gap_overlap_or_inconsistent_total(
    tmp_path: Path,
    second_offset: int,
    second_total: int,
) -> None:
    first = _write_page(
        tmp_path,
        name="page-0",
        offset=0,
        total=3,
        summaries=[_summary("sr:sport_event:1"), _summary("sr:sport_event:2")],
    )
    second = _write_page(
        tmp_path,
        name="page-x",
        offset=second_offset,
        total=second_total,
        summaries=[_summary("sr:sport_event:3")],
    )
    with pytest.raises(ValueError):
        build_complete_season_summaries((first, second))


def test_season_pagination_rejects_body_header_count_disagreement(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="bad-count",
        offset=0,
        total=1,
        summaries=[_summary("sr:sport_event:1")],
        x_result=2,
    )
    with pytest.raises(ValueError, match="differs from X-Result"):
        build_complete_season_summaries((page,))


def test_season_pagination_rejects_duplicate_event_ids(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="duplicate",
        offset=0,
        total=2,
        summaries=[_summary("sr:sport_event:1"), _summary("sr:sport_event:1")],
    )
    with pytest.raises(ValueError, match="duplicate sport-event IDs"):
        build_complete_season_summaries((page,))


def test_audit_accepts_one_exact_match_started_and_normalizes_utc(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="page",
        offset=0,
        total=1,
        summaries=[_summary("sr:sport_event:1")],
    )
    timeline = _write_timeline(
        tmp_path,
        "sr:sport_event:1",
        _timeline(
            "sr:sport_event:1",
            starts=("2026-09-10T10:03:04-04:00",),
            updated=True,
            updated_time="2026-09-10T15:00:00Z",
        ),
    )

    report = audit_sportradar_start_time_coverage(
        page_pairs=(page,), timeline_paths=(timeline,)
    )

    assert report.played_terminal_count == 1
    assert report.exact_match_started_count == 1
    assert report.exact_coverage_rate == 1.0
    assert report.updated_match_started_count == 1
    assert report.events[0].match_started_time == "2026-09-10T14:03:04+00:00"
    assert report.events[0].disposition == "EXACT_MATCH_STARTED"


def test_missing_timeline_is_retained_as_source_failure(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="page",
        offset=0,
        total=1,
        summaries=[_summary("sr:sport_event:1")],
    )
    report = audit_sportradar_start_time_coverage(page_pairs=(page,), timeline_paths=())

    assert report.played_terminal_count == 1
    assert report.missing_timeline_count == 1
    assert report.exact_coverage_rate == 0.0
    assert report.events[0].disposition == "MISSING_TIMELINE"


def test_missing_and_conflicting_match_started_are_not_rescued(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="page",
        offset=0,
        total=2,
        summaries=[_summary("sr:sport_event:1"), _summary("sr:sport_event:2")],
    )
    missing = _write_timeline(
        tmp_path, "sr:sport_event:1", _timeline("sr:sport_event:1", starts=())
    )
    conflicting = _write_timeline(
        tmp_path,
        "sr:sport_event:2",
        _timeline(
            "sr:sport_event:2",
            starts=("2026-09-10T14:01:00Z", "2026-09-10T14:02:00Z"),
        ),
    )
    report = audit_sportradar_start_time_coverage(
        page_pairs=(page,), timeline_paths=(missing, conflicting)
    )

    assert report.missing_match_started_count == 1
    assert report.conflicting_match_started_count == 1
    assert report.exact_match_started_count == 0
    assert report.exact_coverage_rate == 0.0


@pytest.mark.parametrize("bad_time", ("not-a-time", "2026-09-10T14:03:04"))
def test_invalid_or_naive_match_started_time_fails_closed(
    tmp_path: Path, bad_time: str
) -> None:
    page = _write_page(
        tmp_path,
        name="page",
        offset=0,
        total=1,
        summaries=[_summary("sr:sport_event:1")],
    )
    timeline = _write_timeline(
        tmp_path,
        "sr:sport_event:1",
        _timeline("sr:sport_event:1", starts=(bad_time,)),
    )
    report = audit_sportradar_start_time_coverage(
        page_pairs=(page,), timeline_paths=(timeline,)
    )
    assert report.invalid_match_started_time_count == 1
    assert report.exact_match_started_count == 0


def test_walkover_is_retained_but_not_in_played_denominator(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="page",
        offset=0,
        total=2,
        summaries=[
            _summary("sr:sport_event:1", winning_reason="walkover"),
            _summary("sr:sport_event:2"),
        ],
    )
    played = _write_timeline(
        tmp_path, "sr:sport_event:2", _timeline("sr:sport_event:2")
    )
    report = audit_sportradar_start_time_coverage(
        page_pairs=(page,), timeline_paths=(played,)
    )

    assert report.in_scope_count == 2
    assert report.walkover_count == 1
    assert report.played_terminal_count == 1
    assert report.exact_match_started_count == 1
    assert report.exact_coverage_rate == 1.0


def test_lower_tier_and_doubles_stay_out_of_main_tour_scope(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="page",
        offset=0,
        total=3,
        summaries=[
            _summary("sr:sport_event:1", category_id="sr:category:9", category_name="ITF"),
            _summary("sr:sport_event:2", competition_type="doubles"),
            _summary(
                "sr:sport_event:3",
                category_id="sr:category:6",
                category_name="WTA",
            ),
        ],
    )
    timeline = _write_timeline(
        tmp_path, "sr:sport_event:3", _timeline("sr:sport_event:3")
    )
    report = audit_sportradar_start_time_coverage(
        page_pairs=(page,), timeline_paths=(timeline,)
    )

    assert report.raw_summary_count == 3
    assert report.in_scope_count == 1
    assert report.atp_count == 0
    assert report.wta_count == 1


def test_duplicate_retained_timeline_for_same_event_is_rejected(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="page",
        offset=0,
        total=1,
        summaries=[_summary("sr:sport_event:1")],
    )
    first_dir = tmp_path / "a"
    second_dir = tmp_path / "b"
    first_dir.mkdir()
    second_dir.mkdir()
    first = _write_timeline(first_dir, "sr:sport_event:1", _timeline("sr:sport_event:1"))
    second = _write_timeline(second_dir, "sr:sport_event:1", _timeline("sr:sport_event:1"))

    with pytest.raises(ValueError, match="duplicate retained timeline"):
        audit_sportradar_start_time_coverage(
            page_pairs=(page,), timeline_paths=(first, second)
        )


def test_raw_byte_change_changes_source_identity(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="page",
        offset=0,
        total=1,
        summaries=[_summary("sr:sport_event:1")],
    )
    timeline = _write_timeline(
        tmp_path, "sr:sport_event:1", _timeline("sr:sport_event:1")
    )
    first = audit_sportradar_start_time_coverage(
        page_pairs=(page,), timeline_paths=(timeline,)
    )

    payload = json.loads(timeline.read_text(encoding="utf-8"))
    payload["provider_note"] = "retained-byte-change"
    timeline.write_text(json.dumps(payload), encoding="utf-8")
    changed = audit_sportradar_start_time_coverage(
        page_pairs=(page,), timeline_paths=(timeline,)
    )

    assert first.timeline_bundle_sha256 != changed.timeline_bundle_sha256
    assert first.semantic_sha256 != changed.semantic_sha256
