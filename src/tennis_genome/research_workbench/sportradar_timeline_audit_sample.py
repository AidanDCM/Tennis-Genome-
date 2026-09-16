from __future__ import annotations

import hashlib
from datetime import date
from typing import Literal

from pydantic import field_validator, model_validator

from .contracts import WorkbenchRecord
from .sportradar_exact_time_panel import (
    parse_season_inventory_bytes,
    verify_season_inventory_integrity,
)
from .sportradar_season_summaries_census import SeasonSummariesCensus

SAMPLE_PLAN_ID = "SPORTRADAR-TIMELINE-QUALITY-AUDIT-SAMPLE-001"
SELECTION_SEED = "tennis-genome-sportradar-timeline-quality-audit-v1"
PILOT_PROMISING_EXACT_COVERAGE = 0.95
PILOT_MIXED_EXACT_COVERAGE = 0.80

Era = Literal["OLD", "MID", "RECENT"]
LevelFamily = Literal["MAJOR", "ELITE", "TOUR", "OTHER"]
Tour = Literal["ATP", "WTA"]

_MODEL_SCOPE_LEVELS = frozenset(
    {
        "grand_slam",
        "atp_1000",
        "atp_500",
        "atp_250",
        "atp_world_tour_finals",
        "atp_next_generation",
        "wta_1000",
        "wta_500",
        "wta_250",
        "wta_championships",
    }
)


class TimelineAuditSampleRow(WorkbenchRecord):
    tour: Tour
    era: Era
    level_family: LevelFamily
    competition_id: str
    competition_name: str
    competition_level: str | None
    season_id: str
    season_start_date: str
    season_end_date: str
    required_timeline_count: int
    season_summaries_sha256: str
    deterministic_rank_sha256: str

    @field_validator("required_timeline_count")
    @classmethod
    def _positive_timeline_count(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("sampled seasons must require at least one timeline call")
        return value


class TimelineAuditSamplePlan(WorkbenchRecord):
    sample_plan_id: Literal["SPORTRADAR-TIMELINE-QUALITY-AUDIT-SAMPLE-001"] = (
        SAMPLE_PLAN_ID
    )
    selection_seed: Literal["tennis-genome-sportradar-timeline-quality-audit-v1"] = (
        SELECTION_SEED
    )
    inventory_semantic_sha256: str
    census_semantic_sha256: str
    request_budget_cap: int
    max_seasons: int
    selected_timeline_count: int
    selected_season_count: int
    selected_rows: tuple[TimelineAuditSampleRow, ...]
    covered_tour_era_strata: tuple[str, ...]
    unavailable_tour_era_strata: tuple[str, ...]
    pilot_promising_exact_coverage_threshold: float = PILOT_PROMISING_EXACT_COVERAGE
    pilot_mixed_exact_coverage_threshold: float = PILOT_MIXED_EXACT_COVERAGE
    conflict_or_invalid_timestamps_required_for_promising: int = 0

    @model_validator(mode="after")
    def _reproduce_counts(self) -> "TimelineAuditSamplePlan":
        if self.request_budget_cap <= 0:
            raise ValueError("request_budget_cap must be positive")
        if self.max_seasons <= 0:
            raise ValueError("max_seasons must be positive")
        if self.selected_season_count != len(self.selected_rows):
            raise ValueError("selected season count does not reproduce")
        if self.selected_timeline_count != sum(
            row.required_timeline_count for row in self.selected_rows
        ):
            raise ValueError("selected timeline count does not reproduce")
        if self.selected_timeline_count > self.request_budget_cap:
            raise ValueError("sample exceeds request budget cap")
        ids = [row.season_id for row in self.selected_rows]
        if len(ids) != len(set(ids)):
            raise ValueError("sample contains duplicate seasons")
        return self


def _era(start_date: str) -> Era:
    year = date.fromisoformat(start_date).year
    if year <= 2018:
        return "OLD"
    if year <= 2022:
        return "MID"
    return "RECENT"


def _level_family(level: str | None) -> LevelFamily:
    normalized = (level or "").strip().lower()
    if normalized == "grand_slam":
        return "MAJOR"
    if normalized in {
        "atp_1000",
        "atp_world_tour_finals",
        "wta_1000",
        "wta_championships",
    }:
        return "ELITE"
    if normalized in {
        "atp_500",
        "atp_250",
        "atp_next_generation",
        "wta_500",
        "wta_250",
    }:
        return "TOUR"
    return "OTHER"


def _rank_sha(inventory_sha: str, season_id: str) -> str:
    payload = f"{SELECTION_SEED}|{inventory_sha}|{season_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _stratum_name(tour: Tour, era: Era) -> str:
    return f"{tour}:{era}"


def build_timeline_audit_sample_plan(
    *,
    inventory_content: bytes,
    census: SeasonSummariesCensus,
    request_budget_cap: int,
    max_seasons: int = 12,
) -> TimelineAuditSamplePlan:
    """Choose whole historical seasons before any timeline quality is observed.

    Selection uses only frozen provider inventory metadata and the census-derived number
    of timeline calls required for each complete season. It never inspects timeline
    payloads, match_started coverage, scores, winners, or model outcomes.
    """

    if request_budget_cap <= 0:
        raise ValueError("request_budget_cap must be positive")
    if max_seasons <= 0:
        raise ValueError("max_seasons must be positive")

    inventory = parse_season_inventory_bytes(inventory_content)
    verify_season_inventory_integrity(inventory)
    if census.inventory_semantic_sha256 != inventory.semantic_sha256:
        raise ValueError("census is detached from the supplied season inventory")
    if census.historical_candidate_count != inventory.historical_candidate_count:
        raise ValueError("census historical denominator differs from inventory")

    competition_by_id = {
        row.competition_id: row for row in inventory.competition_rows
    }
    season_by_id = {row.season_id: row for row in inventory.season_rows}
    if len(season_by_id) != len(inventory.season_rows):
        raise ValueError("inventory contains duplicate season IDs")

    candidates: list[TimelineAuditSampleRow] = []
    for census_row in census.rows:
        if census_row.disposition != "SUMMARIES_CAPTURED":
            continue
        if census_row.required_timeline_count <= 0:
            continue
        if census_row.season_summaries_sha256 is None:
            raise ValueError("captured season with timeline demand lacks summaries hash")
        season = season_by_id.get(census_row.season_id)
        if season is None or season.status != "HISTORICAL_CANDIDATE":
            raise ValueError("census season is missing from historical inventory")
        if season.competition_id != census_row.competition_id:
            raise ValueError("census/inventory competition mismatch")
        competition = competition_by_id.get(season.competition_id)
        if competition is None:
            raise ValueError("season competition missing from inventory")
        level = (competition.level or "").strip().lower() or None
        if level not in _MODEL_SCOPE_LEVELS:
            continue
        candidates.append(
            TimelineAuditSampleRow(
                tour=season.tour,
                era=_era(season.start_date),
                level_family=_level_family(level),
                competition_id=season.competition_id,
                competition_name=season.competition_name,
                competition_level=level,
                season_id=season.season_id,
                season_start_date=season.start_date,
                season_end_date=season.end_date,
                required_timeline_count=census_row.required_timeline_count,
                season_summaries_sha256=census_row.season_summaries_sha256,
                deterministic_rank_sha256=_rank_sha(
                    inventory.semantic_sha256, season.season_id
                ),
            )
        )

    candidates.sort(
        key=lambda row: (
            row.deterministic_rank_sha256,
            row.season_id,
        )
    )
    fixed_strata: tuple[tuple[Tour, Era], ...] = (
        ("ATP", "OLD"),
        ("WTA", "OLD"),
        ("ATP", "MID"),
        ("WTA", "MID"),
        ("ATP", "RECENT"),
        ("WTA", "RECENT"),
    )

    selected: list[TimelineAuditSampleRow] = []
    selected_ids: set[str] = set()
    remaining = request_budget_cap

    def take_first(pool: list[TimelineAuditSampleRow]) -> bool:
        nonlocal remaining
        for row in pool:
            if row.season_id in selected_ids:
                continue
            if row.required_timeline_count > remaining:
                continue
            selected.append(row)
            selected_ids.add(row.season_id)
            remaining -= row.required_timeline_count
            return True
        return False

    covered: set[str] = set()
    unavailable: set[str] = set()
    for tour, era in fixed_strata:
        pool = [row for row in candidates if row.tour == tour and row.era == era]
        if not pool:
            unavailable.add(_stratum_name(tour, era))
            continue
        if len(selected) < max_seasons and take_first(pool):
            covered.add(_stratum_name(tour, era))

    # Second pass diversifies tournament scale within each tour, still without looking
    # at any timeline quality. Stable hash order resolves ties.
    for tour in ("ATP", "WTA"):
        for family in ("MAJOR", "ELITE", "TOUR"):
            if len(selected) >= max_seasons:
                break
            if any(row.tour == tour and row.level_family == family for row in selected):
                continue
            pool = [
                row
                for row in candidates
                if row.tour == tour and row.level_family == family
            ]
            take_first(pool)

    # Fill remaining budget in the same deterministic rank order. The cost is used only
    # as a hard feasibility constraint, never as a ranking signal.
    for row in candidates:
        if len(selected) >= max_seasons:
            break
        if row.season_id in selected_ids:
            continue
        if row.required_timeline_count <= remaining:
            selected.append(row)
            selected_ids.add(row.season_id)
            remaining -= row.required_timeline_count

    if not selected:
        raise ValueError("no complete historical season fits the timeline request budget")

    selected.sort(key=lambda row: (row.tour, row.era, row.season_start_date, row.season_id))
    return TimelineAuditSamplePlan(
        inventory_semantic_sha256=inventory.semantic_sha256,
        census_semantic_sha256=census.semantic_sha256,
        request_budget_cap=request_budget_cap,
        max_seasons=max_seasons,
        selected_timeline_count=sum(row.required_timeline_count for row in selected),
        selected_season_count=len(selected),
        selected_rows=tuple(selected),
        covered_tour_era_strata=tuple(sorted(covered)),
        unavailable_tour_era_strata=tuple(sorted(unavailable)),
    )


def classify_timeline_quality_pilot(
    *,
    exact_match_started_count: int,
    played_terminal_count: int,
    conflicting_match_started_count: int,
    invalid_match_started_time_count: int,
) -> Literal["PILOT_PROMISING", "PILOT_MIXED", "PILOT_POOR"]:
    if played_terminal_count <= 0:
        raise ValueError("pilot classification requires played terminal matches")
    if not 0 <= exact_match_started_count <= played_terminal_count:
        raise ValueError("exact count must be within played terminal denominator")
    if conflicting_match_started_count < 0 or invalid_match_started_time_count < 0:
        raise ValueError("failure counts must be non-negative")
    coverage = exact_match_started_count / played_terminal_count
    if (
        coverage >= PILOT_PROMISING_EXACT_COVERAGE
        and conflicting_match_started_count == 0
        and invalid_match_started_time_count == 0
    ):
        return "PILOT_PROMISING"
    if coverage >= PILOT_MIXED_EXACT_COVERAGE:
        return "PILOT_MIXED"
    return "PILOT_POOR"
