from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, time
from typing import Literal

from pydantic import field_validator

from .contracts import WorkbenchRecord

SOURCE_ID = "API-TENNIS-HISTORICAL-ENRICHMENT-001"
_ALLOWED_TYPES = {"Atp Singles": "ATP", "Wta Singles": "WTA"}
_TERMINAL_EXCLUSIONS = {"Cancelled", "Retired", "Walk Over"}
_REQUIRED_STAT_NAMES = (
    "Aces",
    "Double Faults",
    "1st serve percentage",
    "1st serve points won",
    "2nd serve points won",
    "Break Points Saved",
    "1st return points won",
    "2nd return points won",
    "Break Points Converted",
    "Service Points Won",
    "Return Points Won",
    "Total Points Won",
    "Service games won",
    "Return games won",
    "Total games won",
)


class ApiTennisPlayerMatchStats(WorkbenchRecord):
    player_key: int
    aces: int
    double_faults: int
    first_serve_pct: float
    first_serve_points_won: int
    first_serve_points_total: int
    second_serve_points_won: int
    second_serve_points_total: int
    break_points_saved: int
    break_points_faced: int
    first_return_points_won: int
    first_return_points_total: int
    second_return_points_won: int
    second_return_points_total: int
    break_points_converted: int
    break_point_opportunities: int
    service_points_won: int
    service_points_total: int
    return_points_won: int
    return_points_total: int
    total_points_won: int
    total_points_total: int
    service_games_won: int
    service_games_total: int
    return_games_won: int
    return_games_total: int
    total_games_won: int
    total_games_total: int

    @field_validator("first_serve_pct")
    @classmethod
    def _probability(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("first_serve_pct must be in [0, 1]")
        return value


class ApiTennisMatchEnrichment(WorkbenchRecord):
    source_id: Literal["API-TENNIS-HISTORICAL-ENRICHMENT-001"] = SOURCE_ID
    event_key: int
    tour: Literal["ATP", "WTA"]
    event_date: str
    scheduled_time_utc: str
    actual_start_time_admissible: Literal[False] = False
    player_a_name: str
    player_a_key: int
    player_b_name: str
    player_b_key: int
    winner_side: Literal["A", "B"]
    tournament_name: str
    tournament_key: int
    tournament_round: str
    tournament_season: str
    qualification: bool
    player_a_stats: ApiTennisPlayerMatchStats
    player_b_stats: ApiTennisPlayerMatchStats
    pointbypoint_game_count: int
    score_set_count: int
    raw_match_sha256: str

    @field_validator("event_date")
    @classmethod
    def _date(cls, value: str) -> str:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("event_date must be canonical YYYY-MM-DD")
        return value

    @field_validator("scheduled_time_utc")
    @classmethod
    def _time(cls, value: str) -> str:
        parsed = time.fromisoformat(value)
        if parsed.strftime("%H:%M") != value:
            raise ValueError("scheduled_time_utc must be HH:MM")
        return value

    @field_validator("raw_match_sha256")
    @classmethod
    def _sha(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("raw_match_sha256 must be lowercase SHA-256")
        return value


class ApiTennisEnrichmentBatch(WorkbenchRecord):
    source_id: Literal["API-TENNIS-HISTORICAL-ENRICHMENT-001"] = SOURCE_ID
    requested_date: str
    raw_response_sha256: str
    admitted_records: tuple[ApiTennisMatchEnrichment, ...]
    exclusion_counts: tuple[tuple[str, int], ...]


def _require_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def _parse_percent(value: object, *, field: str) -> float:
    if not isinstance(value, str) or not value.endswith("%"):
        raise ValueError(f"{field} must be a percentage string")
    return float(value[:-1]) / 100.0


def _parse_qualification(value: object) -> bool:
    if value is True:
        return True
    if value is False or value is None:
        return False
    if type(value) is int:
        if value == 1:
            return True
        if value == 0:
            return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true"}:
            return True
        if normalized in {"0", "false"}:
            return False
    raise ValueError("event_qualification must be a recognized boolean value")


def _stat_lookup(statistics: list[object], *, player_key: int) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for item in statistics:
        if not isinstance(item, dict):
            raise ValueError("statistics must contain JSON objects")
        if item.get("stat_period") != "match" or item.get("player_key") != player_key:
            continue
        name = item.get("stat_name")
        if isinstance(name, str):
            result[name] = item
    missing = [name for name in _REQUIRED_STAT_NAMES if name not in result]
    if missing:
        raise ValueError("missing required match statistics: " + ", ".join(missing))
    return result


def _won_total(stats: dict[str, dict[str, object]], name: str) -> tuple[int, int]:
    row = stats[name]
    won = _require_int(row.get("stat_won"), field=f"{name}.stat_won")
    total = _require_int(row.get("stat_total"), field=f"{name}.stat_total")
    if won < 0 or total < 0 or won > total:
        raise ValueError(f"invalid won/total pair for {name}")
    return won, total


def _plain_int(stats: dict[str, dict[str, object]], name: str) -> int:
    raw = stats[name].get("stat_value")
    if not isinstance(raw, str):
        raise ValueError(f"{name}.stat_value must be a string")
    value = int(raw)
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _build_player_stats(
    statistics: list[object], *, player_key: int
) -> ApiTennisPlayerMatchStats:
    stats = _stat_lookup(statistics, player_key=player_key)
    first_serve_won, first_serve_total = _won_total(stats, "1st serve points won")
    second_serve_won, second_serve_total = _won_total(stats, "2nd serve points won")
    bp_saved, bp_faced = _won_total(stats, "Break Points Saved")
    first_return_won, first_return_total = _won_total(stats, "1st return points won")
    second_return_won, second_return_total = _won_total(stats, "2nd return points won")
    bp_converted, bp_opportunities = _won_total(stats, "Break Points Converted")
    service_won, service_total = _won_total(stats, "Service Points Won")
    return_won, return_total = _won_total(stats, "Return Points Won")
    total_won, total_total = _won_total(stats, "Total Points Won")
    service_games_won, service_games_total = _won_total(stats, "Service games won")
    return_games_won, return_games_total = _won_total(stats, "Return games won")
    total_games_won, total_games_total = _won_total(stats, "Total games won")
    return ApiTennisPlayerMatchStats(
        player_key=player_key,
        aces=_plain_int(stats, "Aces"),
        double_faults=_plain_int(stats, "Double Faults"),
        first_serve_pct=_parse_percent(
            stats["1st serve percentage"].get("stat_value"),
            field="1st serve percentage",
        ),
        first_serve_points_won=first_serve_won,
        first_serve_points_total=first_serve_total,
        second_serve_points_won=second_serve_won,
        second_serve_points_total=second_serve_total,
        break_points_saved=bp_saved,
        break_points_faced=bp_faced,
        first_return_points_won=first_return_won,
        first_return_points_total=first_return_total,
        second_return_points_won=second_return_won,
        second_return_points_total=second_return_total,
        break_points_converted=bp_converted,
        break_point_opportunities=bp_opportunities,
        service_points_won=service_won,
        service_points_total=service_total,
        return_points_won=return_won,
        return_points_total=return_total,
        total_points_won=total_won,
        total_points_total=total_total,
        service_games_won=service_games_won,
        service_games_total=service_games_total,
        return_games_won=return_games_won,
        return_games_total=return_games_total,
        total_games_won=total_games_won,
        total_games_total=total_games_total,
    )


def _canonical_match_sha(row: dict[str, object]) -> str:
    payload = json.dumps(
        row,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def parse_api_tennis_match_enrichment(
    row: dict[str, object],
) -> ApiTennisMatchEnrichment:
    event_type = row.get("event_type_type")
    if event_type not in _ALLOWED_TYPES:
        raise ValueError("match is not ATP/WTA singles")
    if row.get("event_status") != "Finished":
        raise ValueError("match is not a normal finished match")
    winner = row.get("event_winner")
    if winner not in {"First Player", "Second Player"}:
        raise ValueError("finished match is missing an unambiguous winner")
    statistics = row.get("statistics")
    if not isinstance(statistics, list) or not statistics:
        raise ValueError("finished match has no statistics")
    pointbypoint = row.get("pointbypoint")
    if not isinstance(pointbypoint, list):
        raise ValueError("pointbypoint must be an array")
    scores = row.get("scores")
    if not isinstance(scores, list):
        raise ValueError("scores must be an array")

    player_a_key = _require_int(row.get("first_player_key"), field="first_player_key")
    player_b_key = _require_int(row.get("second_player_key"), field="second_player_key")
    event_key = _require_int(row.get("event_key"), field="event_key")
    tournament_key = _require_int(row.get("tournament_key"), field="tournament_key")
    return ApiTennisMatchEnrichment(
        event_key=event_key,
        tour=_ALLOWED_TYPES[str(event_type)],
        event_date=str(row.get("event_date", "")),
        scheduled_time_utc=str(row.get("event_time", "")),
        player_a_name=str(row.get("event_first_player", "")),
        player_a_key=player_a_key,
        player_b_name=str(row.get("event_second_player", "")),
        player_b_key=player_b_key,
        winner_side="A" if winner == "First Player" else "B",
        tournament_name=str(row.get("tournament_name", "")),
        tournament_key=tournament_key,
        tournament_round=str(row.get("tournament_round", "")),
        tournament_season=str(row.get("tournament_season", "")),
        qualification=_parse_qualification(row.get("event_qualification")),
        player_a_stats=_build_player_stats(statistics, player_key=player_a_key),
        player_b_stats=_build_player_stats(statistics, player_key=player_b_key),
        pointbypoint_game_count=len(pointbypoint),
        score_set_count=len(scores),
        raw_match_sha256=_canonical_match_sha(row),
    )


def build_api_tennis_enrichment_batch(
    raw: bytes, *, requested_date: str
) -> ApiTennisEnrichmentBatch:
    if date.fromisoformat(requested_date).isoformat() != requested_date:
        raise ValueError("requested_date must be canonical YYYY-MM-DD")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("success") not in {1, "1"}:
        raise ValueError("API-Tennis response did not report success")
    rows = payload.get("result")
    if not isinstance(rows, list):
        raise ValueError("API-Tennis result must be an array")

    admitted: list[ApiTennisMatchEnrichment] = []
    exclusions: Counter[str] = Counter()
    seen_event_keys: set[int] = set()
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError("API-Tennis fixtures must contain JSON objects")
        event_type = item.get("event_type_type")
        if event_type not in _ALLOWED_TYPES:
            exclusions["NOT_MAIN_TOUR_SINGLES"] += 1
            continue
        status = str(item.get("event_status", ""))
        if status in _TERMINAL_EXCLUSIONS:
            exclusions[status.upper().replace(" ", "_")] += 1
            continue
        if status != "Finished":
            exclusions["NOT_FINISHED"] += 1
            continue
        try:
            record = parse_api_tennis_match_enrichment(item)
        except ValueError:
            exclusions["MISSING_OR_INVALID_ENRICHMENT"] += 1
            continue
        if record.event_date != requested_date:
            exclusions["DATE_MISMATCH"] += 1
            continue
        if record.event_key in seen_event_keys:
            raise ValueError("duplicate API-Tennis event_key in one response")
        seen_event_keys.add(record.event_key)
        admitted.append(record)

    admitted.sort(
        key=lambda record: (
            record.event_date,
            record.scheduled_time_utc,
            record.event_key,
        )
    )
    return ApiTennisEnrichmentBatch(
        requested_date=requested_date,
        raw_response_sha256=hashlib.sha256(raw).hexdigest(),
        admitted_records=tuple(admitted),
        exclusion_counts=tuple(sorted(exclusions.items())),
    )
