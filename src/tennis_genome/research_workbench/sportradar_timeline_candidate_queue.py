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

QUEUE_ID = "SPORTRADAR-TIMELINE-CANDIDATE-QUEUE-001"
QUEUE_SEED = "tennis-genome-sportradar-timeline-candidate-queue-v1"

Era = Literal["OLD", "MID", "RECENT"]
Tour = Literal["ATP", "WTA"]
LevelFamily = Literal["MAJOR", "ELITE", "TOUR"]

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


def _era(start_date: str) -> Era:
    year = date.fromisoformat(start_date).year
    if year <= 2018:
        return "OLD"
    if year <= 2022:
        return "MID"
    return "RECENT"


def _family(level: str) -> LevelFamily:
    if level == "grand_slam":
        return "MAJOR"
    if level in {
        "atp_1000",
        "atp_world_tour_finals",
        "wta_1000",
        "wta_championships",
    }:
        return "ELITE"
    return "TOUR"


def _rank(inventory_sha: str, season_id: str) -> str:
    value = f"{QUEUE_SEED}|{inventory_sha}|{season_id}".encode()
    return hashlib.sha256(value).hexdigest()


class TimelineCandidateQueueRow(WorkbenchRecord):
    queue_position: int
    stratum_position: int
    tour: Tour
    era: Era
    level_family: LevelFamily
    competition_id: str
    competition_name: str
    competition_level: str
    season_id: str
    season_name: str
    season_start_date: str
    season_end_date: str
    deterministic_rank_sha256: str

    @field_validator("queue_position", "stratum_position")
    @classmethod
    def _positive_positions(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("queue positions must be positive")
        return value


class TimelineCandidateQueue(WorkbenchRecord):
    queue_id: Literal["SPORTRADAR-TIMELINE-CANDIDATE-QUEUE-001"] = QUEUE_ID
    selection_seed: Literal["tennis-genome-sportradar-timeline-candidate-queue-v1"] = (
        QUEUE_SEED
    )
    inventory_semantic_sha256: str
    candidates_per_tour_era_stratum: int
    candidate_count: int
    rows: tuple[TimelineCandidateQueueRow, ...]
    covered_strata: tuple[str, ...]
    unavailable_strata: tuple[str, ...]

    @model_validator(mode="after")
    def _reproduce(self) -> "TimelineCandidateQueue":
        if self.candidates_per_tour_era_stratum <= 0:
            raise ValueError("candidates_per_tour_era_stratum must be positive")
        if self.candidate_count != len(self.rows):
            raise ValueError("candidate_count does not reproduce")
        positions = [row.queue_position for row in self.rows]
        if positions != list(range(1, len(self.rows) + 1)):
            raise ValueError("queue positions must be contiguous and ordered")
        ids = [row.season_id for row in self.rows]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate queue contains duplicate seasons")
        return self


def build_timeline_candidate_queue(
    *,
    inventory_content: bytes,
    candidates_per_tour_era_stratum: int = 5,
) -> TimelineCandidateQueue:
    """Freeze a provider-quality-blind queue using inventory metadata only.

    The queue is fixed before any Season Summaries or Timeline endpoint quality is
    observed. Cost probes may later inspect only pagination headers for these seasons.
    """

    if candidates_per_tour_era_stratum <= 0:
        raise ValueError("candidates_per_tour_era_stratum must be positive")
    inventory = parse_season_inventory_bytes(inventory_content)
    verify_season_inventory_integrity(inventory)
    competition_by_id = {
        row.competition_id: row for row in inventory.competition_rows
    }
    strata: tuple[tuple[Tour, Era], ...] = (
        ("ATP", "OLD"),
        ("WTA", "OLD"),
        ("ATP", "MID"),
        ("WTA", "MID"),
        ("ATP", "RECENT"),
        ("WTA", "RECENT"),
    )
    selected_raw: list[tuple[Tour, Era, object, object, str]] = []
    covered: list[str] = []
    unavailable: list[str] = []
    for tour, era in strata:
        pool: list[tuple[str, object, object, str]] = []
        for season in inventory.season_rows:
            if season.status != "HISTORICAL_CANDIDATE" or season.tour != tour:
                continue
            if _era(season.start_date) != era:
                continue
            competition = competition_by_id.get(season.competition_id)
            if competition is None:
                raise ValueError("season competition missing from inventory")
            level = (competition.level or "").strip().lower()
            if level not in _MODEL_SCOPE_LEVELS:
                continue
            pool.append(
                (
                    _rank(inventory.semantic_sha256, season.season_id),
                    season,
                    competition,
                    level,
                )
            )
        pool.sort(key=lambda item: (item[0], item[1].season_id))
        if not pool:
            unavailable.append(f"{tour}:{era}")
            continue
        covered.append(f"{tour}:{era}")
        for rank, season, competition, level in pool[
            :candidates_per_tour_era_stratum
        ]:
            selected_raw.append((tour, era, season, competition, rank))

    # Interleave by stratum position so a bounded probe sees broad coverage before
    # spending calls on additional backups from any one era/tour.
    by_stratum: dict[tuple[Tour, Era], list[tuple[object, object, str]]] = {}
    for tour, era, season, competition, rank in selected_raw:
        by_stratum.setdefault((tour, era), []).append((season, competition, rank))
    rows: list[TimelineCandidateQueueRow] = []
    queue_position = 1
    for stratum_position in range(1, candidates_per_tour_era_stratum + 1):
        for tour, era in strata:
            items = by_stratum.get((tour, era), [])
            if len(items) < stratum_position:
                continue
            season, competition, rank = items[stratum_position - 1]
            level = (competition.level or "").strip().lower()
            rows.append(
                TimelineCandidateQueueRow(
                    queue_position=queue_position,
                    stratum_position=stratum_position,
                    tour=tour,
                    era=era,
                    level_family=_family(level),
                    competition_id=season.competition_id,
                    competition_name=season.competition_name,
                    competition_level=level,
                    season_id=season.season_id,
                    season_name=season.season_name,
                    season_start_date=season.start_date,
                    season_end_date=season.end_date,
                    deterministic_rank_sha256=rank,
                )
            )
            queue_position += 1

    if not rows:
        raise ValueError("inventory provides no model-scope historical queue candidates")
    return TimelineCandidateQueue(
        inventory_semantic_sha256=inventory.semantic_sha256,
        candidates_per_tour_era_stratum=candidates_per_tour_era_stratum,
        candidate_count=len(rows),
        rows=tuple(rows),
        covered_strata=tuple(covered),
        unavailable_strata=tuple(unavailable),
    )
