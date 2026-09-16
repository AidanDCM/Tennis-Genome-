from __future__ import annotations

from typing import Literal

from pydantic import field_validator, model_validator

from .contracts import WorkbenchRecord
from .sportradar_timeline_candidate_queue import TimelineCandidateQueue
from .sportradar_timeline_cost_probe import TimelineCostProbe

PLAN_ID = "SPORTRADAR-TIMELINE-QUALITY-AUDIT-SAMPLE-002"


class TimelineAuditSampleV2Row(WorkbenchRecord):
    selection_position: int
    queue_position: int
    stratum_position: int
    tour: str
    era: str
    level_family: str
    competition_id: str
    competition_name: str
    competition_level: str
    season_id: str
    season_name: str
    season_start_date: str
    season_end_date: str
    timeline_request_upper_bound: int
    additional_summary_page_upper_bound: int
    first_page_body_sha256: str
    first_page_headers_sha256: str

    @field_validator(
        "selection_position",
        "queue_position",
        "stratum_position",
        "timeline_request_upper_bound",
        "additional_summary_page_upper_bound",
    )
    @classmethod
    def _nonnegative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("sample V2 integer fields must be non-negative")
        return value


class TimelineAuditSampleV2(WorkbenchRecord):
    plan_id: Literal["SPORTRADAR-TIMELINE-QUALITY-AUDIT-SAMPLE-002"] = PLAN_ID
    queue_semantic_sha256: str
    cost_probe_semantic_sha256: str
    timeline_request_budget_cap: int
    max_seasons: int
    selected_season_count: int
    selected_timeline_upper_bound: int
    selected_additional_summary_page_upper_bound: int
    covered_tour_era_strata: tuple[str, ...]
    selected_rows: tuple[TimelineAuditSampleV2Row, ...]

    @model_validator(mode="after")
    def _reproduce(self) -> "TimelineAuditSampleV2":
        if self.timeline_request_budget_cap <= 0:
            raise ValueError("timeline_request_budget_cap must be positive")
        if self.max_seasons <= 0:
            raise ValueError("max_seasons must be positive")
        if self.selected_season_count != len(self.selected_rows):
            raise ValueError("selected_season_count does not reproduce")
        if self.selected_timeline_upper_bound != sum(
            row.timeline_request_upper_bound for row in self.selected_rows
        ):
            raise ValueError("selected timeline upper bound does not reproduce")
        if self.selected_timeline_upper_bound > self.timeline_request_budget_cap:
            raise ValueError("selected sample exceeds timeline request budget")
        if self.selected_additional_summary_page_upper_bound != sum(
            row.additional_summary_page_upper_bound for row in self.selected_rows
        ):
            raise ValueError("summary page upper bound does not reproduce")
        positions = [row.selection_position for row in self.selected_rows]
        if positions != list(range(1, len(self.selected_rows) + 1)):
            raise ValueError("selection positions must be contiguous")
        return self


def build_timeline_audit_sample_v2(
    *,
    queue: TimelineCandidateQueue,
    probe: TimelineCostProbe,
    timeline_request_budget_cap: int,
    max_seasons: int = 6,
) -> TimelineAuditSampleV2:
    """Select whole seasons using metadata + first-page cost only.

    No Timeline endpoint payload, match_started evidence, score, winner, or model output
    is available to this function. X-Max-Results is treated conservatively as the
    timeline-call upper bound for a complete sampled season.
    """

    if probe.queue_semantic_sha256 != queue.semantic_sha256:
        raise ValueError("cost probe is detached from candidate queue")
    if timeline_request_budget_cap <= 0:
        raise ValueError("timeline_request_budget_cap must be positive")
    if max_seasons <= 0:
        raise ValueError("max_seasons must be positive")

    queue_by_position = {row.queue_position: row for row in queue.rows}
    probe_by_position = {row.queue_position: row for row in probe.rows}
    if len(queue_by_position) != len(queue.rows):
        raise ValueError("candidate queue positions are not unique")
    if len(probe_by_position) != len(probe.rows):
        raise ValueError("cost probe positions are not unique")

    candidates: list[tuple[object, object]] = []
    for position in sorted(probe_by_position):
        probe_row = probe_by_position[position]
        queue_row = queue_by_position.get(position)
        if queue_row is None or queue_row.season_id != probe_row.season_id:
            raise ValueError("cost probe row does not match candidate queue")
        if probe_row.disposition != "PROBED":
            continue
        if probe_row.total_event_upper_bound <= 0:
            continue
        candidates.append((queue_row, probe_row))

    selected: list[tuple[object, object]] = []
    selected_ids: set[str] = set()
    remaining = timeline_request_budget_cap

    def take(pool: list[tuple[object, object]]) -> bool:
        nonlocal remaining
        for queue_row, probe_row in pool:
            if queue_row.season_id in selected_ids:
                continue
            cost = probe_row.total_event_upper_bound
            if cost > remaining:
                continue
            selected.append((queue_row, probe_row))
            selected_ids.add(queue_row.season_id)
            remaining -= cost
            return True
        return False

    # Primary objective: breadth across ATP/WTA and old/mid/recent strata.
    strata = (
        "ATP:OLD",
        "WTA:OLD",
        "ATP:MID",
        "WTA:MID",
        "ATP:RECENT",
        "WTA:RECENT",
    )
    for stratum in strata:
        if len(selected) >= max_seasons:
            break
        pool = [
            item
            for item in candidates
            if f"{item[0].tour}:{item[0].era}" == stratum
        ]
        take(pool)

    # Secondary objective: representation of major/elite/tour scale where possible.
    for family in ("MAJOR", "ELITE", "TOUR"):
        if len(selected) >= max_seasons:
            break
        if any(queue_row.level_family == family for queue_row, _ in selected):
            continue
        pool = [item for item in candidates if item[0].level_family == family]
        take(pool)

    # Fill remaining budget strictly in frozen queue order.
    for item in candidates:
        if len(selected) >= max_seasons:
            break
        queue_row, probe_row = item
        if queue_row.season_id in selected_ids:
            continue
        if probe_row.total_event_upper_bound <= remaining:
            selected.append(item)
            selected_ids.add(queue_row.season_id)
            remaining -= probe_row.total_event_upper_bound

    if not selected:
        raise ValueError("no probed whole season fits the timeline request budget")

    rows = tuple(
        TimelineAuditSampleV2Row(
            selection_position=index,
            queue_position=queue_row.queue_position,
            stratum_position=queue_row.stratum_position,
            tour=queue_row.tour,
            era=queue_row.era,
            level_family=queue_row.level_family,
            competition_id=queue_row.competition_id,
            competition_name=queue_row.competition_name,
            competition_level=queue_row.competition_level,
            season_id=queue_row.season_id,
            season_name=queue_row.season_name,
            season_start_date=queue_row.season_start_date,
            season_end_date=queue_row.season_end_date,
            timeline_request_upper_bound=probe_row.total_event_upper_bound,
            additional_summary_page_upper_bound=probe_row.additional_summary_page_upper_bound,
            first_page_body_sha256=probe_row.response_body_sha256,
            first_page_headers_sha256=probe_row.response_headers_sha256,
        )
        for index, (queue_row, probe_row) in enumerate(selected, start=1)
    )
    return TimelineAuditSampleV2(
        queue_semantic_sha256=queue.semantic_sha256,
        cost_probe_semantic_sha256=probe.semantic_sha256,
        timeline_request_budget_cap=timeline_request_budget_cap,
        max_seasons=max_seasons,
        selected_season_count=len(rows),
        selected_timeline_upper_bound=sum(row.timeline_request_upper_bound for row in rows),
        selected_additional_summary_page_upper_bound=sum(
            row.additional_summary_page_upper_bound for row in rows
        ),
        covered_tour_era_strata=tuple(
            sorted({f"{row.tour}:{row.era}" for row in rows})
        ),
        selected_rows=rows,
    )
