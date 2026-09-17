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
from tennis_genome.research_workbench.sportradar_timeline_sample_capture import (
    capture_timeline_audit_sample,
)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _summary(event_id: str) -> dict[str, object]:
    return {
        "sport_event": {
            "id": event_id,
            "start_time": "2025-01-03T15:00:00+00:00",
            "start_time_confirmed": True,
            "sport_event_context": {
                "category": {"id": "sr:category:6", "name": "WTA"},
                "competition": {
                    "id": "sr:competition:20",
                    "name": "WTA Test Singles",
                    "type": "singles",
                },
                "season": {
                    "id": "sr:season:203",
                    "competition_id": "sr:competition:20",
                    "start_date": "2025-01-01",
                },
            },
        },
        "sport_event_status": {"status": "closed"},
    }


def _write_source_evidence(tmp_path: Path) -> tuple[Path, str]:
    census_root = tmp_path / "census-root"
    season_dir = census_root / "seasons" / "sr_season_203"
    season_dir.mkdir(parents=True)
    raw = season_dir / "page-000-offset-000000.json"
    headers = season_dir / "page-000-offset-000000.headers"
    raw.write_text(
        json.dumps(
            {
                "generated_at": "2026-09-17T12:00:00+00:00",
                "summaries": [
                    _summary("sr:sport_event:1"),
                    _summary("sr:sport_event:2"),
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    headers.write_text(
        "HTTP/1.1 200\nX-Max-Results: 2\nX-Offset: 0\nX-Result: 2\n",
        encoding="iso-8859-1",
    )
    aggregate = build_complete_season_summaries(((raw, headers),))
    return census_root, hashlib.sha256(_canonical_json(aggregate)).hexdigest()


def _write_plan_and_census(tmp_path: Path) -> tuple[Path, Path, Path]:
    census_root, summaries_sha = _write_source_evidence(tmp_path)
    row = SeasonSummariesCensusRow(
        tour="WTA",
        competition_id="sr:competition:20",
        season_id="sr:season:203",
        disposition="SUMMARIES_CAPTURED",
        page_count=1,
        raw_summary_count=2,
        played_terminal_count=2,
        walkover_count=0,
        nonterminal_count=0,
        required_timeline_count=2,
        required_timeline_event_ids=("sr:sport_event:1", "sr:sport_event:2"),
        season_summaries_sha256=summaries_sha,
        access_failure_semantic_sha256=None,
    )
    census = SeasonSummariesCensus(
        inventory_semantic_sha256="a" * 64,
        inventory_snapshot_at="2026-09-17T12:00:00+00:00",
        access_level="trial",
        historical_candidate_count=1,
        summaries_captured_count=1,
        history_not_available_count=0,
        provider_request_count=1,
        total_raw_summary_count=2,
        total_played_terminal_count=2,
        total_walkover_count=0,
        total_nonterminal_count=0,
        total_required_timeline_count=2,
        rows=(row,),
    )
    plan = TimelineAuditSamplePlan(
        inventory_semantic_sha256="a" * 64,
        census_semantic_sha256=census.semantic_sha256,
        request_budget_cap=2,
        max_seasons=1,
        selected_timeline_count=2,
        selected_season_count=1,
        selected_rows=(
            TimelineAuditSampleRow(
                tour="WTA",
                era="RECENT",
                level_family="TOUR",
                competition_id="sr:competition:20",
                competition_name="WTA Test Singles",
                competition_level="wta_250",
                season_id="sr:season:203",
                season_start_date="2025-01-01",
                season_end_date="2025-01-10",
                required_timeline_count=2,
                season_summaries_sha256=summaries_sha,
                deterministic_rank_sha256="b" * 64,
            ),
        ),
        covered_tour_era_strata=("WTA:RECENT",),
        unavailable_tour_era_strata=(),
    )
    plan_path = tmp_path / "plan.json"
    census_path = tmp_path / "census.json"
    plan_path.write_text(
        json.dumps(plan.canonical_payload(), sort_keys=True), encoding="utf-8"
    )
    census_path.write_text(
        json.dumps(census.canonical_payload(), sort_keys=True), encoding="utf-8"
    )
    return plan_path, census_path, census_root


def _timeline(event_id: str, *, started: str) -> ProviderHttpResponse:
    return ProviderHttpResponse(
        status=200,
        body=json.dumps(
            {
                "generated_at": "2026-09-17T12:01:00+00:00",
                "sport_event": {"id": event_id},
                "timeline": [{"type": "match_started", "time": started}],
            },
            sort_keys=True,
        ).encode(),
        headers=(("Content-Type", "application/json"),),
    )


def test_capture_admits_complete_exact_time_season(tmp_path: Path) -> None:
    plan_path, census_path, census_root = _write_plan_and_census(tmp_path)
    responses = iter(
        (
            _timeline("sr:sport_event:1", started="2025-01-03T15:02:00+00:00"),
            _timeline("sr:sport_event:2", started="2025-01-04T15:05:00+00:00"),
        )
    )

    capture = capture_timeline_audit_sample(
        sample_plan_path=plan_path,
        census_path=census_path,
        census_root=census_root,
        output_dir=tmp_path / "capture",
        repo_root=Path("."),
        access_level="trial",
        api_key="test-key",
        provider_get=lambda _url, _headers: next(responses),
        sleeper=lambda _seconds: None,
    )

    assert capture.provider_request_count == 2
    assert capture.captured_timeline_count == 2
    assert capture.history_not_available_count == 0
    assert capture.admitted_season_count == 1
    assert capture.rejected_season_count == 0
    assert capture.rows[0].admission_status == "ADMITTED"
    assert capture.rows[0].admission_failure_reasons == ()
    assert (tmp_path / "capture" / "seasons" / "sr_season_203" / "admission-receipt.json").is_file()


def test_capture_retains_404_as_source_quality_failure(tmp_path: Path) -> None:
    plan_path, census_path, census_root = _write_plan_and_census(tmp_path)
    responses = iter(
        (
            _timeline("sr:sport_event:1", started="2025-01-03T15:02:00+00:00"),
            ProviderHttpResponse(status=404, body=b"{}", headers=()),
        )
    )

    capture = capture_timeline_audit_sample(
        sample_plan_path=plan_path,
        census_path=census_path,
        census_root=census_root,
        output_dir=tmp_path / "capture",
        repo_root=Path("."),
        access_level="trial",
        api_key="test-key",
        provider_get=lambda _url, _headers: next(responses),
        sleeper=lambda _seconds: None,
    )

    assert capture.captured_timeline_count == 1
    assert capture.history_not_available_count == 1
    assert capture.admitted_season_count == 0
    assert capture.rejected_season_count == 1
    assert "MISSING_TIMELINE" in capture.rows[0].admission_failure_reasons
    assert capture.rows[0].admission_receipt_semantic_sha256 is None


def test_capture_aborts_on_transient_provider_failure(tmp_path: Path) -> None:
    plan_path, census_path, census_root = _write_plan_and_census(tmp_path)

    with pytest.raises(RuntimeError, match="transient HTTP 500"):
        capture_timeline_audit_sample(
            sample_plan_path=plan_path,
            census_path=census_path,
            census_root=census_root,
            output_dir=tmp_path / "capture",
            repo_root=Path("."),
            access_level="trial",
            api_key="test-key",
            provider_get=lambda _url, _headers: ProviderHttpResponse(
                status=500,
                body=b"{}",
                headers=(),
            ),
            sleeper=lambda _seconds: None,
        )


def test_capture_rejects_wrong_timeline_identity(tmp_path: Path) -> None:
    plan_path, census_path, census_root = _write_plan_and_census(tmp_path)

    with pytest.raises(ValueError, match="identity differs"):
        capture_timeline_audit_sample(
            sample_plan_path=plan_path,
            census_path=census_path,
            census_root=census_root,
            output_dir=tmp_path / "capture",
            repo_root=Path("."),
            access_level="trial",
            api_key="test-key",
            provider_get=lambda _url, _headers: _timeline(
                "sr:sport_event:wrong",
                started="2025-01-03T15:02:00+00:00",
            ),
            sleeper=lambda _seconds: None,
        )
