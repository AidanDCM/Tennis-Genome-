from __future__ import annotations

import json
from pathlib import Path

import pytest

from tennis_genome.research_workbench.sportradar_start_time_admission import (
    ADMISSION_STATUS,
    admit_exact_time_audit_bytes,
)
from tennis_genome.research_workbench.sportradar_start_time_audit_v2 import (
    AUDIT_ID,
    audit_sportradar_start_time_coverage_v2,
)


def _summary(
    event_id: str,
    *,
    category_id: str = "sr:category:3",
    category_name: str = "ATP",
    competition_id: str = "sr:competition:100",
    competition_name: str = "Test Open",
    competition_type: str = "singles",
    season_id: str = "sr:season:2026",
    season_start_date: str = "2026-09-07",
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
                    "id": competition_id,
                    "name": competition_name,
                    "type": competition_type,
                },
                "season": {
                    "id": season_id,
                    "start_date": season_start_date,
                    "competition_id": competition_id,
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
    events: list[dict[str, object]] = []
    for start in starts:
        row: dict[str, object] = {"type": "match_started", "time": start}
        if updated:
            row["updated"] = True
        if updated_time is not None:
            row["updated_time"] = updated_time
        events.append(row)
    return {"sport_event": {"id": event_id}, "timeline": events}


def _write_page(
    root: Path,
    *,
    name: str,
    summaries: list[dict[str, object]],
    offset: int = 0,
    total: int | None = None,
) -> tuple[Path, Path]:
    raw = root / f"{name}.json"
    headers = root / f"{name}.headers.txt"
    raw.write_text(json.dumps({"summaries": summaries}), encoding="utf-8")
    expected_total = len(summaries) if total is None else total
    headers.write_text(
        f"X-Max-Results: {expected_total}\n"
        f"X-Offset: {offset}\n"
        f"X-Result: {len(summaries)}\n",
        encoding="utf-8",
    )
    return raw, headers


def _write_timeline(root: Path, event_id: str, payload: dict[str, object]) -> Path:
    path = root / f"timeline-{event_id.rsplit(':', 1)[-1]}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _render(report: object) -> bytes:
    payload = report.canonical_payload()  # type: ignore[attr-defined]
    return (json.dumps(payload, sort_keys=True, allow_nan=False) + "\n").encode()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_v2_binds_one_exact_provider_season(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="page",
        summaries=[_summary("sr:sport_event:1"), _summary("sr:sport_event:2")],
    )
    timelines = (
        _write_timeline(tmp_path, "sr:sport_event:1", _timeline("sr:sport_event:1")),
        _write_timeline(tmp_path, "sr:sport_event:2", _timeline("sr:sport_event:2")),
    )

    report = audit_sportradar_start_time_coverage_v2(
        page_pairs=(page,), timeline_paths=timelines
    )

    assert report.audit_id == AUDIT_ID
    assert report.season.season_id == "sr:season:2026"
    assert report.season.competition_id == "sr:competition:100"
    assert report.season.category_id == "sr:category:3"
    assert report.base_audit.exact_coverage_rate == 1.0


def test_v2_rejects_mixed_season_identity(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="mixed",
        summaries=[
            _summary("sr:sport_event:1"),
            _summary("sr:sport_event:2", season_id="sr:season:other"),
        ],
    )
    with pytest.raises(ValueError, match="mixes provider season identities"):
        audit_sportradar_start_time_coverage_v2(page_pairs=(page,), timeline_paths=())


def test_v2_rejects_timeline_outside_season_denominator(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="page",
        summaries=[_summary("sr:sport_event:1")],
    )
    extra = _write_timeline(
        tmp_path, "sr:sport_event:999", _timeline("sr:sport_event:999")
    )
    with pytest.raises(ValueError, match="outside the Season Summaries denominator"):
        audit_sportradar_start_time_coverage_v2(
            page_pairs=(page,), timeline_paths=(extra,)
        )


def test_complete_atp_season_is_admitted_for_chronology_only(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="atp",
        summaries=[
            _summary("sr:sport_event:1"),
            _summary("sr:sport_event:2", winning_reason="walkover"),
            _summary("sr:sport_event:3", winning_reason="retirement"),
        ],
    )
    timelines = (
        _write_timeline(tmp_path, "sr:sport_event:1", _timeline("sr:sport_event:1")),
        _write_timeline(
            tmp_path,
            "sr:sport_event:3",
            _timeline(
                "sr:sport_event:3",
                updated=True,
                updated_time="2026-09-10T15:00:00Z",
            ),
        ),
    )
    report = audit_sportradar_start_time_coverage_v2(
        page_pairs=(page,), timeline_paths=timelines
    )

    receipt = admit_exact_time_audit_bytes(_render(report), repo_root=_repo_root())

    assert receipt.admission_status == ADMISSION_STATUS
    assert receipt.tour == "ATP"
    assert receipt.played_terminal_count == 2
    assert receipt.exact_match_started_count == 2
    assert receipt.walkover_count == 1
    assert receipt.updated_match_started_count == 1


def test_complete_wta_season_can_pass_same_frozen_gate(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="wta",
        summaries=[
            _summary(
                "sr:sport_event:1",
                category_id="sr:category:6",
                category_name="WTA",
                competition_id="sr:competition:200",
                competition_name="WTA Test Open",
                season_id="sr:season:wta-2026",
            )
        ],
    )
    timeline = _write_timeline(
        tmp_path, "sr:sport_event:1", _timeline("sr:sport_event:1")
    )
    report = audit_sportradar_start_time_coverage_v2(
        page_pairs=(page,), timeline_paths=(timeline,)
    )

    receipt = admit_exact_time_audit_bytes(_render(report), repo_root=_repo_root())
    assert receipt.tour == "WTA"


def test_one_missing_start_rejects_season_instead_of_using_percentage(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="page",
        summaries=[_summary("sr:sport_event:1"), _summary("sr:sport_event:2")],
    )
    exact = _write_timeline(
        tmp_path, "sr:sport_event:1", _timeline("sr:sport_event:1")
    )
    missing = _write_timeline(
        tmp_path, "sr:sport_event:2", _timeline("sr:sport_event:2", starts=())
    )
    report = audit_sportradar_start_time_coverage_v2(
        page_pairs=(page,), timeline_paths=(exact, missing)
    )

    with pytest.raises(ValueError, match="MISSING_MATCH_STARTED"):
        admit_exact_time_audit_bytes(_render(report), repo_root=_repo_root())


def test_nonterminal_row_blocks_completed_season_admission(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="page",
        summaries=[
            _summary("sr:sport_event:1"),
            _summary("sr:sport_event:2", status="scheduled"),
        ],
    )
    exact = _write_timeline(
        tmp_path, "sr:sport_event:1", _timeline("sr:sport_event:1")
    )
    report = audit_sportradar_start_time_coverage_v2(
        page_pairs=(page,), timeline_paths=(exact,)
    )

    with pytest.raises(ValueError, match="SEASON_NOT_COMPLETE"):
        admit_exact_time_audit_bytes(_render(report), repo_root=_repo_root())


def test_updated_start_without_update_timestamp_is_rejected(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="page",
        summaries=[_summary("sr:sport_event:1")],
    )
    timeline = _write_timeline(
        tmp_path,
        "sr:sport_event:1",
        _timeline("sr:sport_event:1", updated=True),
    )
    report = audit_sportradar_start_time_coverage_v2(
        page_pairs=(page,), timeline_paths=(timeline,)
    )

    with pytest.raises(ValueError, match="lacks retained updated_time"):
        admit_exact_time_audit_bytes(_render(report), repo_root=_repo_root())


def test_tampered_aggregate_count_is_rejected(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="page",
        summaries=[_summary("sr:sport_event:1")],
    )
    timeline = _write_timeline(
        tmp_path, "sr:sport_event:1", _timeline("sr:sport_event:1")
    )
    report = audit_sportradar_start_time_coverage_v2(
        page_pairs=(page,), timeline_paths=(timeline,)
    )
    payload = report.canonical_payload()
    base = payload["base_audit"]
    assert isinstance(base, dict)
    base["exact_match_started_count"] = 0

    with pytest.raises(ValueError, match="exact-start count does not reproduce"):
        admit_exact_time_audit_bytes(
            (json.dumps(payload) + "\n").encode(), repo_root=_repo_root()
        )


def test_doubles_season_cannot_be_admitted_as_main_tour_singles(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        name="doubles",
        summaries=[_summary("sr:sport_event:1", competition_type="doubles")],
    )
    report = audit_sportradar_start_time_coverage_v2(
        page_pairs=(page,), timeline_paths=()
    )

    with pytest.raises(ValueError, match="singles competition season"):
        admit_exact_time_audit_bytes(_render(report), repo_root=_repo_root())