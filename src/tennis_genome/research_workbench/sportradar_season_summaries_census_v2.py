from __future__ import annotations

import json
from pathlib import Path

from . import sportradar_season_summaries_census as v1
from .sportradar_exact_time_panel import (
    build_provider_access_failure_evidence,
    parse_season_inventory_bytes,
    verify_season_inventory_integrity,
)
from .sportradar_season_inventory import SeasonInventoryRow
from .sportradar_start_time_audit import build_complete_season_summaries
from .sportradar_start_time_audit_v2 import derive_single_season_identity


def _capture_one_season(
    *,
    season: SeasonInventoryRow,
    output_dir: Path,
    access_level: str,
    api_key: str,
    provider_get: v1.ProviderGet,
    sleeper: v1.Sleeper,
    now: v1.Now,
    request_counter: list[int],
) -> v1.SeasonSummariesCensusRow:
    season_dir = output_dir / "seasons" / season.season_id.replace(":", "_")
    page_pairs: list[tuple[Path, Path]] = []
    expected_total: int | None = None
    start = 0
    for page_number in range(v1._MAX_PAGES):
        if request_counter[0] and access_level == "trial":
            sleeper(v1._TRIAL_MIN_REQUEST_INTERVAL_SECONDS)
        response = provider_get(
            v1._url(access_level=access_level, season_id=season.season_id, start=start),
            {"x-api-key": api_key, "Accept": "application/json"},
        )
        request_counter[0] += 1
        raw_path, headers_path = v1._retain_response(
            season_dir=season_dir,
            page_number=page_number,
            start=start,
            response=response,
        )
        if response.status in {404, 410}:
            if page_number != 0 or start != 0:
                raise ValueError("Season Summaries became unavailable mid-pagination")
            attempted = now()
            if attempted.tzinfo is None or attempted.utcoffset() is None:
                raise ValueError("capture clock must be timezone-aware")
            evidence = build_provider_access_failure_evidence(
                season=season,
                endpoint_path=f"seasons/{season.season_id}/summaries.json",
                attempted_at=attempted,
                http_status=response.status,
                response_headers_path=headers_path,
                response_body_path=raw_path,
            )
            (season_dir / "access-failure.json").write_text(
                json.dumps(evidence.canonical_payload(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return v1.SeasonSummariesCensusRow(
                tour=season.tour,
                competition_id=season.competition_id,
                season_id=season.season_id,
                disposition="HISTORY_NOT_AVAILABLE",
                page_count=0,
                raw_summary_count=0,
                played_terminal_count=0,
                walkover_count=0,
                nonterminal_count=0,
                required_timeline_count=0,
                required_timeline_event_ids=(),
                season_summaries_sha256=None,
                access_failure_semantic_sha256=evidence.semantic_sha256,
            )
        if response.status in {401, 403}:
            raise RuntimeError(
                f"Season Summaries authentication/authorization failed with HTTP {response.status}"
            )
        total, offset, result_count = v1._validate_page(
            response,
            expected_start=start,
            expected_total=expected_total,
        )
        if expected_total is None:
            expected_total = total
        page_pairs.append((raw_path, headers_path))
        next_start = offset + result_count
        if next_start == total:
            break
        if next_start <= start:
            raise ValueError("Season Summaries pagination did not advance")
        start = next_start
    else:
        raise ValueError("Season Summaries pagination exceeded frozen page maximum")

    aggregate = build_complete_season_summaries(page_pairs)
    summaries = aggregate.get("summaries")
    if not isinstance(summaries, list):
        raise AssertionError("complete Season Summaries aggregate lacks summaries")
    aggregate_sha = v1._sha256_bytes(v1._canonical_json(aggregate))

    # A historical season may legitimately exist in the provider catalog while its
    # summaries endpoint returns an authenticated, pagination-complete zero-row page.
    # Preserve that evidence as a successfully captured empty denominator instead of
    # inventing an identity from nonexistent matches or treating it as access failure.
    if not summaries:
        return v1.SeasonSummariesCensusRow(
            tour=season.tour,
            competition_id=season.competition_id,
            season_id=season.season_id,
            disposition="SUMMARIES_CAPTURED",
            page_count=len(page_pairs),
            raw_summary_count=0,
            played_terminal_count=0,
            walkover_count=0,
            nonterminal_count=0,
            required_timeline_count=0,
            required_timeline_event_ids=(),
            season_summaries_sha256=aggregate_sha,
            access_failure_semantic_sha256=None,
        )

    identity = derive_single_season_identity(summaries)
    if identity.season_id != season.season_id:
        raise ValueError("Season Summaries season identity differs from frozen inventory")
    if identity.competition_id != season.competition_id:
        raise ValueError("Season Summaries competition differs from frozen inventory")
    played, walkovers, nonterminal, timeline_ids = v1._event_census(aggregate)
    return v1.SeasonSummariesCensusRow(
        tour=season.tour,
        competition_id=season.competition_id,
        season_id=season.season_id,
        disposition="SUMMARIES_CAPTURED",
        page_count=len(page_pairs),
        raw_summary_count=len(summaries),
        played_terminal_count=played,
        walkover_count=walkovers,
        nonterminal_count=nonterminal,
        required_timeline_count=len(timeline_ids),
        required_timeline_event_ids=timeline_ids,
        season_summaries_sha256=aggregate_sha,
        access_failure_semantic_sha256=None,
    )


def capture_season_summaries_census(
    *,
    inventory_path: Path,
    output_dir: Path,
    access_level: str,
    api_key: str,
    provider_get: v1.ProviderGet = v1._default_provider_get,
    sleeper: v1.Sleeper = v1.time.sleep,
    now: v1.Now = v1._default_now,
) -> v1.SeasonSummariesCensus:
    if access_level not in v1._ALLOWED_ACCESS:
        raise ValueError("Sportradar access level must be trial or production")
    if not api_key.strip():
        raise ValueError("SPORTRADAR_API_KEY must be configured")
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError("Season Summaries census output directory must begin empty")

    inventory = parse_season_inventory_bytes(inventory_path.read_bytes())
    verify_season_inventory_integrity(inventory)
    candidates = tuple(
        sorted(
            (row for row in inventory.season_rows if row.status == "HISTORICAL_CANDIDATE"),
            key=lambda row: (row.tour, row.competition_id, row.start_date, row.season_id),
        )
    )
    if len(candidates) != inventory.historical_candidate_count:
        raise AssertionError("historical candidate count detached from frozen inventory")

    request_counter = [0]
    rows = tuple(
        _capture_one_season(
            season=season,
            output_dir=output_dir,
            access_level=access_level,
            api_key=api_key,
            provider_get=provider_get,
            sleeper=sleeper,
            now=now,
            request_counter=request_counter,
        )
        for season in candidates
    )
    captured = sum(row.disposition == "SUMMARIES_CAPTURED" for row in rows)
    unavailable = sum(row.disposition == "HISTORY_NOT_AVAILABLE" for row in rows)
    census = v1.SeasonSummariesCensus(
        inventory_semantic_sha256=inventory.semantic_sha256,
        inventory_snapshot_at=inventory.snapshot_at,
        access_level=access_level,
        historical_candidate_count=inventory.historical_candidate_count,
        summaries_captured_count=captured,
        history_not_available_count=unavailable,
        provider_request_count=request_counter[0],
        total_raw_summary_count=sum(row.raw_summary_count for row in rows),
        total_played_terminal_count=sum(row.played_terminal_count for row in rows),
        total_walkover_count=sum(row.walkover_count for row in rows),
        total_nonterminal_count=sum(row.nonterminal_count for row in rows),
        total_required_timeline_count=sum(row.required_timeline_count for row in rows),
        rows=rows,
    )
    (output_dir / "census.json").write_text(
        json.dumps(census.canonical_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_bytes(
        v1._canonical_json(
            {
                "census_semantic_sha256": census.semantic_sha256,
                "historical_candidate_count": census.historical_candidate_count,
                "history_not_available_count": census.history_not_available_count,
                "provider_request_count": census.provider_request_count,
                "summaries_captured_count": census.summaries_captured_count,
                "total_required_timeline_count": census.total_required_timeline_count,
            }
        )
        + b"\n"
    )
    return census
