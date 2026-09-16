from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tennis_genome.research_workbench.sportradar_season_summaries_census import (
    ProviderHttpResponse,
    SeasonSummariesCensus,
    SeasonSummariesCensusRow,
)
from tennis_genome.research_workbench.sportradar_start_time_audit import (
    build_complete_season_summaries,
)
from tennis_genome.research_workbench.sportradar_timeline_audit_sample import (
    TimelineAuditSamplePlan,
    TimelineAuditSampleRow,
)
from tennis_genome.research_workbench.sportradar_timeline_quality_capture import (
    capture_timeline_quality_pilot,
)

GENERATED = "2026-09-16T18:30:00+00:00"
SEASON_ID = "sr:season:100"
COMPETITION_ID = "sr:competition:10"


def _canonical_sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _summary(event_id: str, start_time: str) -> dict[str, object]:
    return {
        "sport_event": {
            "id": event_id,
            "start_time": start_time,
            "start_time_confirmed": True,
            "estimated": False,
            "sport_event_context": {
                "category": {"id": "sr:category:3", "name": "ATP"},
                "competition": {
                    "id": COMPETITION_ID,
                    "name": "ATP Test",
                    "type": "singles",
                },
                "season": {
                    "id": SEASON_ID,
                    "competition_id": COMPETITION_ID,
                    "start_date": "2025-01-01",
                },
            },
        },
        "sport_event_status": {"status": "closed"},
    }


def _write_census_fixture(
    tmp_path: Path,
    *,
    event_ids: tuple[str, ...],
) -> tuple[Path, Path, Path]:
    census_root = tmp_path / "season-summaries-census"
    season_dir = census_root / "seasons" / "sr_season_100"
    season_dir.mkdir(parents=True)
    summaries = [
        _summary(event_id, f"2025-01-{10 + index:02d}T15:00:00+00:00")
        for index, event_id in enumerate(event_ids)
    ]
    raw = season_dir / "page-000-offset-000000.json"
    headers = season_dir / "page-000-offset-000000.headers"
    raw.write_text(
        json.dumps({"generated_at": GENERATED, "summaries": summaries}, sort_keys=True),
        encoding="utf-8",
    )
    headers.write_text(
        "HTTP/1.1 200\n"
        f"X-Max-Results: {len(summaries)}\n"
        "X-Offset: 0\n"
        f"X-Result: {len(summaries)}\n",
        encoding="iso-8859-1",
    )
    aggregate = build_complete_season_summaries(((raw, headers),))
    aggregate_sha = _canonical_sha(aggregate)
    census_row = SeasonSummariesCensusRow(
        tour="ATP",
        competition_id=COMPETITION_ID,
        season_id=SEASON_ID,
        disposition="SUMMARIES_CAPTURED",
        page_count=1,
        raw_summary_count=len(event_ids),
        played_terminal_count=len(event_ids),
        walkover_count=0,
        nonterminal_count=0,
        required_timeline_count=len(event_ids),
        required_timeline_event_ids=event_ids,
        season_summaries_sha256=aggregate_sha,
        access_failure_semantic_sha256=None,
    )
    census = SeasonSummariesCensus(
        inventory_semantic_sha256="1" * 64,
        inventory_snapshot_at="2026-09-16T19:03:52+00:00",
        access_level="trial",
        historical_candidate_count=1,
        summaries_captured_count=1,
        history_not_available_count=0,
        provider_request_count=1,
        total_raw_summary_count=len(event_ids),
        total_played_terminal_count=len(event_ids),
        total_walkover_count=0,
        total_nonterminal_count=0,
        total_required_timeline_count=len(event_ids),
        rows=(census_row,),
    )
    census_path = census_root / "census.json"
    census_path.write_text(
        json.dumps(census.canonical_payload(), sort_keys=True), encoding="utf-8"
    )
    plan = TimelineAuditSamplePlan(
        inventory_semantic_sha256="1" * 64,
        census_semantic_sha256=census.semantic_sha256,
        request_budget_cap=len(event_ids),
        max_seasons=1,
        selected_timeline_count=len(event_ids),
        selected_season_count=1,
        selected_rows=(
            TimelineAuditSampleRow(
                tour="ATP",
                era="RECENT",
                level_family="TOUR",
                competition_id=COMPETITION_ID,
                competition_name="ATP Test",
                competition_level="atp_250",
                season_id=SEASON_ID,
                season_start_date="2025-01-01",
                season_end_date="2025-02-01",
                required_timeline_count=len(event_ids),
                season_summaries_sha256=aggregate_sha,
                deterministic_rank_sha256="2" * 64,
            ),
        ),
        covered_tour_era_strata=("ATP:RECENT",),
        unavailable_tour_era_strata=(),
    )
    plan_path = tmp_path / "sample-plan.json"
    plan_path.write_text(
        json.dumps(plan.canonical_payload(), sort_keys=True), encoding="utf-8"
    )
    return plan_path, census_path, census_root


def _timeline_response(
    event_id: str,
    *,
    match_started: str | None,
) -> ProviderHttpResponse:
    timeline: list[dict[str, object]] = []
    if match_started is not None:
        timeline.append(
            {
                "id": 1,
                "type": "match_started",
                "time": match_started,
            }
        )
    else:
        timeline.append(
            {
                "id": 1,
                "type": "period_started",
                "time": "2025-01-10T15:10:00+00:00",
            }
        )
    return ProviderHttpResponse(
        status=200,
        body=json.dumps(
            {
                "generated_at": GENERATED,
                "sport_event": {"id": event_id},
                "timeline": timeline,
            },
            sort_keys=True,
        ).encode("utf-8"),
        headers=(("content-type", "application/json"),),
    )


def _status(status: int) -> ProviderHttpResponse:
    return ProviderHttpResponse(
        status=status,
        body=json.dumps({"message": f"HTTP {status}"}).encode("utf-8"),
        headers=(("content-type", "application/json"),),
    )


def test_capture_scores_exact_missing_started_and_missing_timeline(tmp_path: Path) -> None:
    event_ids = (
        "sr:sport_event:1",
        "sr:sport_event:2",
        "sr:sport_event:3",
    )
    plan_path, census_path, census_root = _write_census_fixture(
        tmp_path, event_ids=event_ids
    )
    responses = {
        "sr:sport_event:1": _timeline_response(
            "sr:sport_event:1", match_started="2025-01-10T15:05:00+00:00"
        ),
        "sr:sport_event:2": _timeline_response(
            "sr:sport_event:2", match_started=None
        ),
        "sr:sport_event:3": _status(404),
    }
    sleeps: list[float] = []

    def get(url: str, _headers: dict[str, str]) -> ProviderHttpResponse:
        event_id = next(event_id for event_id in event_ids if event_id in url)
        return responses[event_id]

    report = capture_timeline_quality_pilot(
        sample_plan_path=plan_path,
        census_path=census_path,
        census_root=census_root,
        output_dir=tmp_path / "timeline-audit",
        access_level="trial",
        api_key="secret",
        provider_get=get,
        sleeper=sleeps.append,
    )

    assert report.provider_request_count == 3
    assert report.played_terminal_count == 3
    assert report.exact_match_started_count == 1
    assert report.missing_match_started_count == 1
    assert report.missing_timeline_count == 1
    assert report.exact_coverage_rate == pytest.approx(1 / 3)
    assert report.pilot_disposition == "PILOT_POOR"
    assert report.schedule_drift_pair_count == 1
    assert report.median_signed_schedule_drift_minutes == pytest.approx(5.0)
    assert report.median_absolute_schedule_drift_minutes == pytest.approx(5.0)
    assert report.p90_absolute_schedule_drift_minutes == pytest.approx(5.0)
    assert len(sleeps) == 2
    assert report.strata[0].stratum == "ATP:RECENT"
    assert report.strata[0].exact_coverage_rate == pytest.approx(1 / 3)
    assert (
        tmp_path
        / "timeline-audit"
        / "seasons"
        / "sr_season_100"
        / "timeline-failures"
        / "sr_sport_event_3.body"
    ).is_file()


def test_capture_classifies_complete_exact_sample_as_promising(tmp_path: Path) -> None:
    event_ids = ("sr:sport_event:1", "sr:sport_event:2")
    plan_path, census_path, census_root = _write_census_fixture(
        tmp_path, event_ids=event_ids
    )

    def get(url: str, _headers: dict[str, str]) -> ProviderHttpResponse:
        event_id = next(event_id for event_id in event_ids if event_id in url)
        suffix = int(event_id.rsplit(":", 1)[-1]) - 1
        return _timeline_response(
            event_id,
            match_started=f"2025-01-{10 + suffix:02d}T15:03:00+00:00",
        )

    report = capture_timeline_quality_pilot(
        sample_plan_path=plan_path,
        census_path=census_path,
        census_root=census_root,
        output_dir=tmp_path / "timeline-audit",
        access_level="trial",
        api_key="secret",
        provider_get=get,
        sleeper=lambda _seconds: None,
    )
    assert report.exact_match_started_count == 2
    assert report.exact_coverage_rate == 1.0
    assert report.pilot_disposition == "PILOT_PROMISING"


def test_capture_rejects_timeline_identity_drift_and_does_not_retry_429(
    tmp_path: Path,
) -> None:
    event_ids = ("sr:sport_event:1",)
    plan_path, census_path, census_root = _write_census_fixture(
        tmp_path, event_ids=event_ids
    )
    wrong = _timeline_response(
        "sr:sport_event:999", match_started="2025-01-10T15:05:00+00:00"
    )
    with pytest.raises(ValueError, match="differs from requested event"):
        capture_timeline_quality_pilot(
            sample_plan_path=plan_path,
            census_path=census_path,
            census_root=census_root,
            output_dir=tmp_path / "identity-drift",
            access_level="trial",
            api_key="secret",
            provider_get=lambda _url, _headers: wrong,
            sleeper=lambda _seconds: None,
        )

    calls = 0

    def rate_limited(_url: str, _headers: dict[str, str]) -> ProviderHttpResponse:
        nonlocal calls
        calls += 1
        return _status(429)

    with pytest.raises(RuntimeError, match="HTTP 429"):
        capture_timeline_quality_pilot(
            sample_plan_path=plan_path,
            census_path=census_path,
            census_root=census_root,
            output_dir=tmp_path / "rate-limit",
            access_level="trial",
            api_key="secret",
            provider_get=rate_limited,
            sleeper=lambda _seconds: None,
        )
    assert calls == 1
