from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Literal

from pydantic import model_validator

from . import sportradar_season_summaries_census as v1
from . import sportradar_season_summaries_census_v2 as v2
from .contracts import WorkbenchRecord
from .sportradar_exact_time_panel import (
    ProviderAccessFailureEvidence,
    parse_season_inventory_bytes,
    verify_season_inventory_integrity,
)
from .sportradar_season_inventory import SeasonInventoryRow
from .sportradar_start_time_audit import build_complete_season_summaries
from .sportradar_start_time_audit_v2 import derive_single_season_identity

CHECKPOINT_ID = "SPORTRADAR-HISTORICAL-SEASON-SUMMARIES-CHECKPOINT-001"
_HTTP_STATUS_RE = re.compile(r"^HTTP/\S+\s+(\d{3})(?:\s|$)", re.IGNORECASE)


class CensusResumeCheckpoint(WorkbenchRecord):
    checkpoint_id: Literal[
        "SPORTRADAR-HISTORICAL-SEASON-SUMMARIES-CHECKPOINT-001"
    ] = CHECKPOINT_ID
    inventory_semantic_sha256: str
    historical_candidate_count: int
    completed_candidate_count: int
    next_candidate_index: int
    next_season_id: str | None
    retained_provider_response_count: int
    reusable_provider_response_count: int
    quota_exhausted: bool
    quota_failure_status: int | None
    quota_failure_season_id: str | None
    rows: tuple[v1.SeasonSummariesCensusRow, ...]

    @model_validator(mode="after")
    def _reproduce(self) -> CensusResumeCheckpoint:
        if self.historical_candidate_count < 0:
            raise ValueError("historical candidate count must be non-negative")
        if self.completed_candidate_count != len(self.rows):
            raise ValueError("completed candidate count does not reproduce from rows")
        if self.next_candidate_index != self.completed_candidate_count:
            raise ValueError("checkpoint frontier must follow the completed prefix")
        if not 0 <= self.next_candidate_index <= self.historical_candidate_count:
            raise ValueError("checkpoint frontier is outside the frozen denominator")
        if self.reusable_provider_response_count > self.retained_provider_response_count:
            raise ValueError("reusable response count cannot exceed retained responses")
        season_ids = [row.season_id for row in self.rows]
        if len(season_ids) != len(set(season_ids)):
            raise ValueError("checkpoint contains duplicate season rows")
        if self.next_candidate_index == self.historical_candidate_count:
            if self.next_season_id is not None:
                raise ValueError("complete checkpoint cannot name a next season")
            if self.quota_exhausted:
                raise ValueError("complete checkpoint cannot be quota exhausted")
        elif self.next_season_id is None:
            raise ValueError("incomplete checkpoint must identify the next season")
        if self.quota_exhausted:
            if self.quota_failure_status != 429:
                raise ValueError("quota-exhausted checkpoint must retain HTTP 429")
            if self.quota_failure_season_id != self.next_season_id:
                raise ValueError("quota failure must occur at the checkpoint frontier")
        elif self.quota_failure_status is not None or self.quota_failure_season_id is not None:
            raise ValueError("non-quota checkpoint cannot carry quota failure fields")
        return self


def _safe_id(value: str) -> str:
    return value.replace(":", "_").replace("/", "_")


def _candidates(inventory: object) -> tuple[SeasonInventoryRow, ...]:
    rows = tuple(
        sorted(
            (
                row
                for row in inventory.season_rows  # type: ignore[attr-defined]
                if row.status == "HISTORICAL_CANDIDATE"
            ),
            key=lambda row: (row.tour, row.competition_id, row.start_date, row.season_id),
        )
    )
    if len(rows) != inventory.historical_candidate_count:  # type: ignore[attr-defined]
        raise AssertionError("historical candidate count detached from frozen inventory")
    return rows


def _http_status(headers_path: Path) -> int:
    lines = headers_path.read_text(encoding="iso-8859-1").splitlines()
    if not lines:
        raise ValueError(f"retained response headers are empty: {headers_path}")
    match = _HTTP_STATUS_RE.match(lines[0].strip())
    if match is None:
        raise ValueError(f"retained response headers lack HTTP status: {headers_path}")
    return int(match.group(1))


def _page_pairs(season_dir: Path) -> tuple[tuple[Path, Path], ...]:
    raw_paths = tuple(sorted(season_dir.glob("page-*.json")))
    if not raw_paths:
        raise ValueError(f"season evidence has no retained JSON pages: {season_dir.name}")
    pairs: list[tuple[Path, Path]] = []
    for raw in raw_paths:
        headers = raw.with_suffix(".headers")
        if not headers.is_file():
            raise ValueError(f"retained page lacks headers: {raw}")
        pairs.append((raw, headers))
    return tuple(pairs)


def _reconstruct_completed_row(
    *,
    season: SeasonInventoryRow,
    season_dir: Path,
) -> tuple[v1.SeasonSummariesCensusRow | None, int | None, int]:
    pairs = _page_pairs(season_dir)
    statuses = tuple(_http_status(headers) for _, headers in pairs)
    response_count = len(statuses)

    if any(status == 429 for status in statuses):
        if statuses[-1] != 429 or any(status != 200 for status in statuses[:-1]):
            raise ValueError("quota evidence has an unsupported response sequence")
        return None, 429, response_count

    if statuses[0] in {404, 410}:
        if len(statuses) != 1:
            raise ValueError("history-not-available evidence must be one retained response")
        failure_path = season_dir / "access-failure.json"
        if not failure_path.is_file():
            raise ValueError("history-not-available season lacks access-failure evidence")
        failure = ProviderAccessFailureEvidence.model_validate_json(
            failure_path.read_text(encoding="utf-8")
        )
        if failure.http_status != statuses[0]:
            raise ValueError("access-failure evidence disagrees with retained HTTP status")
        if failure.failure_class != "HISTORY_NOT_AVAILABLE":
            raise ValueError("resume accepts only retained history-not-available access evidence")
        if (
            failure.season_id != season.season_id
            or failure.competition_id != season.competition_id
            or failure.tour != season.tour
        ):
            raise ValueError("access-failure evidence identity differs from frozen inventory")
        return (
            v1.SeasonSummariesCensusRow(
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
                access_failure_semantic_sha256=failure.semantic_sha256,
            ),
            None,
            response_count,
        )

    if any(status != 200 for status in statuses):
        raise ValueError("partial census contains a non-reusable provider response")

    aggregate = build_complete_season_summaries(pairs)
    summaries = aggregate.get("summaries")
    if not isinstance(summaries, list):
        raise AssertionError("complete Season Summaries aggregate lacks summaries")
    aggregate_sha = v1._sha256_bytes(v1._canonical_json(aggregate))
    if not summaries:
        return (
            v1.SeasonSummariesCensusRow(
                tour=season.tour,
                competition_id=season.competition_id,
                season_id=season.season_id,
                disposition="SUMMARIES_CAPTURED",
                page_count=len(pairs),
                raw_summary_count=0,
                played_terminal_count=0,
                walkover_count=0,
                nonterminal_count=0,
                required_timeline_count=0,
                required_timeline_event_ids=(),
                season_summaries_sha256=aggregate_sha,
                access_failure_semantic_sha256=None,
            ),
            None,
            response_count,
        )

    identity = derive_single_season_identity(summaries)
    if identity.season_id != season.season_id:
        raise ValueError("retained summaries season differs from frozen inventory")
    if identity.competition_id != season.competition_id:
        raise ValueError("retained summaries competition differs from frozen inventory")
    played, walkovers, nonterminal, timeline_ids = v1._event_census(aggregate)
    return (
        v1.SeasonSummariesCensusRow(
            tour=season.tour,
            competition_id=season.competition_id,
            season_id=season.season_id,
            disposition="SUMMARIES_CAPTURED",
            page_count=len(pairs),
            raw_summary_count=len(summaries),
            played_terminal_count=played,
            walkover_count=walkovers,
            nonterminal_count=nonterminal,
            required_timeline_count=len(timeline_ids),
            required_timeline_event_ids=timeline_ids,
            season_summaries_sha256=aggregate_sha,
            access_failure_semantic_sha256=None,
        ),
        None,
        response_count,
    )


def reconstruct_resume_checkpoint(
    *,
    inventory_path: Path,
    partial_census_root: Path,
) -> CensusResumeCheckpoint:
    inventory = parse_season_inventory_bytes(inventory_path.read_bytes())
    verify_season_inventory_integrity(inventory)
    candidates = _candidates(inventory)
    evidence_root = partial_census_root / "seasons"
    if not evidence_root.is_dir():
        raise ValueError("partial census artifact lacks a seasons evidence directory")

    expected_dirs = {_safe_id(row.season_id): row for row in candidates}
    observed_dirs = {path.name for path in evidence_root.iterdir() if path.is_dir()}
    unknown = sorted(observed_dirs - set(expected_dirs))
    if unknown:
        raise ValueError("partial census contains season directories outside inventory")

    completed: list[v1.SeasonSummariesCensusRow] = []
    reusable_count = 0
    retained_count = 0
    quota_status: int | None = None
    quota_season: str | None = None
    frontier = 0

    for index, season in enumerate(candidates):
        season_dir = evidence_root / _safe_id(season.season_id)
        if not season_dir.is_dir():
            frontier = index
            break
        row, pause_status, response_count = _reconstruct_completed_row(
            season=season,
            season_dir=season_dir,
        )
        retained_count += response_count
        if pause_status is not None:
            quota_status = pause_status
            quota_season = season.season_id
            frontier = index
            break
        if row is None:
            raise AssertionError("reusable season reconstruction returned no row")
        completed.append(row)
        reusable_count += response_count
    else:
        frontier = len(candidates)

    allowed_dirs = {_safe_id(row.season_id) for row in candidates[:frontier]}
    if frontier < len(candidates) and quota_status is not None:
        allowed_dirs.add(_safe_id(candidates[frontier].season_id))
    extra_after_frontier = sorted(observed_dirs - allowed_dirs)
    if extra_after_frontier:
        raise ValueError("partial census evidence is not a contiguous candidate prefix")

    next_id = None if frontier == len(candidates) else candidates[frontier].season_id
    return CensusResumeCheckpoint(
        inventory_semantic_sha256=inventory.semantic_sha256,
        historical_candidate_count=inventory.historical_candidate_count,
        completed_candidate_count=len(completed),
        next_candidate_index=frontier,
        next_season_id=next_id,
        retained_provider_response_count=retained_count,
        reusable_provider_response_count=reusable_count,
        quota_exhausted=quota_status == 429,
        quota_failure_status=quota_status,
        quota_failure_season_id=quota_season,
        rows=tuple(completed),
    )


def _write_checkpoint(path: Path, checkpoint: CensusResumeCheckpoint) -> None:
    path.write_text(
        json.dumps(checkpoint.canonical_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _copy_reusable_prefix(
    *,
    partial_census_root: Path,
    output_dir: Path,
    checkpoint: CensusResumeCheckpoint,
) -> None:
    for row in checkpoint.rows:
        source = partial_census_root / "seasons" / _safe_id(row.season_id)
        target = output_dir / "seasons" / _safe_id(row.season_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)


def _checkpoint_from_state(
    *,
    inventory: object,
    candidates: tuple[SeasonInventoryRow, ...],
    rows: list[v1.SeasonSummariesCensusRow],
    output_dir: Path,
    quota_status: int | None,
) -> CensusResumeCheckpoint:
    next_index = len(rows)
    next_id = None if next_index == len(candidates) else candidates[next_index].season_id
    all_headers = tuple((output_dir / "seasons").rglob("page-*.headers"))
    reusable_dirs = {_safe_id(row.season_id) for row in rows}
    reusable_headers = tuple(
        path
        for path in all_headers
        if path.parent.name in reusable_dirs
    )
    return CensusResumeCheckpoint(
        inventory_semantic_sha256=inventory.semantic_sha256,  # type: ignore[attr-defined]
        historical_candidate_count=inventory.historical_candidate_count,  # type: ignore[attr-defined]
        completed_candidate_count=len(rows),
        next_candidate_index=next_index,
        next_season_id=next_id,
        retained_provider_response_count=len(all_headers),
        reusable_provider_response_count=len(reusable_headers),
        quota_exhausted=quota_status == 429,
        quota_failure_status=quota_status,
        quota_failure_season_id=next_id if quota_status == 429 else None,
        rows=tuple(rows),
    )


def resume_season_summaries_census(
    *,
    inventory_path: Path,
    partial_census_root: Path,
    output_dir: Path,
    access_level: str,
    api_key: str,
    provider_get: v1.ProviderGet = v1._default_provider_get,
    sleeper: v1.Sleeper = v1.time.sleep,
    now: v1.Now = v1._default_now,
) -> tuple[v1.SeasonSummariesCensus | None, CensusResumeCheckpoint]:
    if access_level not in v1._ALLOWED_ACCESS:
        raise ValueError("Sportradar access level must be trial or production")
    if not api_key.strip():
        raise ValueError("SPORTRADAR_API_KEY must be configured")
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError("resumed census output directory must begin empty")

    inventory = parse_season_inventory_bytes(inventory_path.read_bytes())
    verify_season_inventory_integrity(inventory)
    candidates = _candidates(inventory)
    source_checkpoint = reconstruct_resume_checkpoint(
        inventory_path=inventory_path,
        partial_census_root=partial_census_root,
    )
    _copy_reusable_prefix(
        partial_census_root=partial_census_root,
        output_dir=output_dir,
        checkpoint=source_checkpoint,
    )
    rows = list(source_checkpoint.rows)
    request_counter = [source_checkpoint.retained_provider_response_count]

    for season in candidates[len(rows) :]:
        try:
            row = v2._capture_one_season(
                season=season,
                output_dir=output_dir,
                access_level=access_level,
                api_key=api_key,
                provider_get=provider_get,
                sleeper=sleeper,
                now=now,
                request_counter=request_counter,
            )
        except ValueError as exc:
            if str(exc) != "Season Summaries returned HTTP 429":
                raise
            checkpoint = _checkpoint_from_state(
                inventory=inventory,
                candidates=candidates,
                rows=rows,
                output_dir=output_dir,
                quota_status=429,
            )
            _write_checkpoint(output_dir / "checkpoint.json", checkpoint)
            return None, checkpoint
        rows.append(row)

    census = v1.SeasonSummariesCensus(
        inventory_semantic_sha256=inventory.semantic_sha256,
        inventory_snapshot_at=inventory.snapshot_at,
        access_level=access_level,
        historical_candidate_count=inventory.historical_candidate_count,
        summaries_captured_count=sum(row.disposition == "SUMMARIES_CAPTURED" for row in rows),
        history_not_available_count=sum(
            row.disposition == "HISTORY_NOT_AVAILABLE" for row in rows
        ),
        provider_request_count=request_counter[0],
        total_raw_summary_count=sum(row.raw_summary_count for row in rows),
        total_played_terminal_count=sum(row.played_terminal_count for row in rows),
        total_walkover_count=sum(row.walkover_count for row in rows),
        total_nonterminal_count=sum(row.nonterminal_count for row in rows),
        total_required_timeline_count=sum(row.required_timeline_count for row in rows),
        rows=tuple(rows),
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
    checkpoint = _checkpoint_from_state(
        inventory=inventory,
        candidates=candidates,
        rows=rows,
        output_dir=output_dir,
        quota_status=None,
    )
    _write_checkpoint(output_dir / "checkpoint.json", checkpoint)
    return census, checkpoint
