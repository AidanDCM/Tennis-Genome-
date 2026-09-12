from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import date

from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, MatchStats, PreMatchState
from tennis_genome.experiments.pattern_confirm_live_identity import (
    IdentityMapping,
    parse_sportradar_prematch_event,
    validate_mapping_against_event,
)

_TARGET_VERSION = "pattern-confirm-sportradar-target-v1"
_STATE_VERSION = "pattern-confirm-sportradar-state-v1"
_STATE_SOURCE = "SPORTRADAR_TENNIS_V3_STATE_V1"
_ATP_CATEGORY_ID = "sr:category:3"
_TOKEN = re.compile(r"[-\s]+")

_SURFACE_MAP = {
    "hardcourt_outdoor": "Hard",
    "hardcourt_indoor": "Hard",
    "hard_court": "Hard",
    "hardcourt": "Hard",
    "hard": "Hard",
    "red_clay": "Clay",
    "green_clay": "Clay",
    "clay": "Clay",
    "grass": "Grass",
    "carpet_indoor": "Carpet",
    "carpet": "Carpet",
    "unknown": "Unknown",
}
_LEVEL_MAP = {
    "grand_slam": "G",
    "atp_1000": "M",
    "atp_world_tour_finals": "F",
    "atp_500": "A",
    "atp_250": "A",
    "atp_next_generation": "A",
}
_ROUND_MAP = {
    "round_of_256": "R256",
    "round_of_128": "R128",
    "round_of_64": "R64",
    "round_of_32": "R32",
    "round_of_16": "R16",
    "quarterfinal": "QF",
    "semifinal": "SF",
    "final": "F",
    "qualification": "Q",
    "qualification_final": "QFNL",
    "qualification_round_1": "Q1",
    "qualification_round_2": "Q2",
    "round_1": "R1",
    "round_2": "R2",
    "round_3": "R3",
}


@dataclass(frozen=True)
class TargetContextArtifact:
    version: str
    source_contract: str
    match_id: str
    sportradar_event_id: str
    season_id: str
    season_start_date: str
    identity_mapping_sha256: str
    summary_sha256: str
    season_info_sha256: str
    profile_a_sha256: str
    profile_b_sha256: str
    pre_match: dict[str, object]
    artifact_sha256: str


@dataclass(frozen=True)
class StateExclusion:
    sport_event_id: str
    reason: str


@dataclass(frozen=True)
class SportradarStateBundle:
    version: str
    source_contract: str
    crosswalk_sha256: str
    source_payload_sha256: str
    parsed_rows_sha256: str
    source_count: int
    accepted_count: int
    excluded_count: int
    max_event_date: str | None
    rows: tuple[dict[str, object], ...]
    exclusions: tuple[StateExclusion, ...]
    artifact_sha256: str


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _self_hash(payload: dict[str, object]) -> str:
    unsigned = dict(payload)
    unsigned.pop("artifact_sha256", None)
    return _sha(_canonical_json(unsigned))


def _as_dict(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _as_list(value: object, *, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    return value


def _text(value: object) -> str:
    return str(value).strip()


def _required_text(raw: dict[str, object], name: str) -> str:
    value = _text(raw.get(name, ""))
    if not value:
        raise ValueError(f"{name} must be non-empty")
    return value


def _positive_int(value: object, *, field: str, optional: bool = True) -> int | None:
    if value is None or _text(value) == "":
        if optional:
            return None
        raise ValueError(f"{field} must be present")
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{field} must be positive")
    return parsed


def _optional_nonnegative_int(value: object, *, field: str) -> int | None:
    if value is None or _text(value) == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"{field} cannot be negative")
    return parsed


def _normalized_enum(value: object) -> str:
    return _TOKEN.sub("_", _text(value).lower())


def map_surface(value: object) -> str:
    normalized = _normalized_enum(value)
    if not normalized:
        return "Unknown"
    mapped = _SURFACE_MAP.get(normalized)
    if mapped is None:
        raise ValueError(f"unrecognized Sportradar surface: {value!r}")
    return mapped


def map_level(value: object) -> str | None:
    normalized = _normalized_enum(value)
    if not normalized:
        return None
    mapped = _LEVEL_MAP.get(normalized)
    if mapped is None:
        raise ValueError(f"unrecognized Sportradar ATP competition level: {value!r}")
    return mapped


def map_round(value: object) -> str | None:
    normalized = _normalized_enum(value)
    if not normalized:
        return None
    mapped = _ROUND_MAP.get(normalized)
    if mapped is None:
        raise ValueError(f"unrecognized Sportradar round: {value!r}")
    return mapped


def map_handedness(value: object) -> str | None:
    normalized = _normalized_enum(value)
    if not normalized:
        return None
    if normalized == "right":
        return "R"
    if normalized == "left":
        return "L"
    raise ValueError(f"unrecognized Sportradar handedness: {value!r}")


def _age_years(dob: object, *, event_date: date) -> float | None:
    if dob is None or not _text(dob):
        return None
    born = date.fromisoformat(_text(dob))
    days = (event_date - born).days
    if days < 0:
        raise ValueError("competitor date_of_birth is after target event date")
    return days / 365.25


def _profile_fields(payload: dict[str, object], expected_id: str, event_date: date) -> dict[str, object]:
    competitor = _as_dict(payload.get("competitor"), field="competitor profile competitor")
    if _required_text(competitor, "id") != expected_id:
        raise ValueError("competitor profile ID mismatch")
    info_raw = payload.get("info", {})
    info = _as_dict(info_raw, field="competitor profile info")
    height = _positive_int(info.get("height"), field="competitor height")
    country = _text(competitor.get("country_code")) or None
    return {
        "age_years": _age_years(info.get("date_of_birth"), event_date=event_date),
        "height_cm": height,
        "hand": map_handedness(info.get("handedness")),
        "ioc": country,
    }


def _summary_context(summary: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    sport_event = _as_dict(summary.get("sport_event"), field="sport_event")
    context = _as_dict(sport_event.get("sport_event_context"), field="sport_event_context")
    return sport_event, context


def _qualified_competitors(sport_event: dict[str, object]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for raw in _as_list(sport_event.get("competitors"), field="sport_event.competitors"):
        competitor = _as_dict(raw, field="sport_event competitor")
        qualifier = _required_text(competitor, "qualifier").lower()
        if qualifier not in {"home", "away"} or qualifier in result:
            raise ValueError("sport-event competitors must have unique home/away qualifiers")
        result[qualifier] = competitor
    if set(result) != {"home", "away"}:
        raise ValueError("sport event requires exactly home and away competitors")
    return result


def _pre_match_payload(state: PreMatchState) -> dict[str, object]:
    payload = asdict(state)
    payload["event_date"] = state.event_date.isoformat()
    return payload


def _pre_match_from_payload(payload: dict[str, object]) -> PreMatchState:
    normalized = dict(payload)
    normalized["event_date"] = date.fromisoformat(str(payload["event_date"]))
    return PreMatchState(**normalized)


def _historical_payload(match: HistoricalMatch) -> dict[str, object]:
    return {
        "pre_match": _pre_match_payload(match.pre_match),
        "outcome": asdict(match.outcome),
        "stats": None if match.stats is None else asdict(match.stats),
    }


def _historical_from_payload(payload: dict[str, object]) -> HistoricalMatch:
    pre = _as_dict(payload.get("pre_match"), field="state row pre_match")
    outcome = _as_dict(payload.get("outcome"), field="state row outcome")
    stats_raw = payload.get("stats")
    stats = None if stats_raw is None else MatchStats(**_as_dict(stats_raw, field="state row stats"))
    return HistoricalMatch(
        pre_match=_pre_match_from_payload(pre),
        outcome=MatchOutcome(**outcome),
        stats=stats,
    )


def _season_info(
    payload: dict[str, object], *, expected_season_id: str, expected_competition_id: str
) -> tuple[str, str | None, int | None]:
    season = _as_dict(payload.get("season"), field="season info season")
    if _required_text(season, "id") != expected_season_id:
        raise ValueError("Season Info season ID mismatch")
    if _required_text(season, "competition_id") != expected_competition_id:
        raise ValueError("Season Info competition ID mismatch")
    competition = _as_dict(season.get("competition"), field="season info competition")
    if _required_text(competition, "id") != expected_competition_id:
        raise ValueError("Season Info nested competition ID mismatch")
    if _required_text(competition, "type").lower() != "singles":
        raise ValueError("Season Info competition must be singles")
    info = _as_dict(season.get("info", {}), field="season info info")
    surface = map_surface(info.get("surface"))
    level = map_level(competition.get("level"))
    draw_size = _positive_int(info.get("number_of_competitors"), field="number_of_competitors")
    return surface, level, draw_size


def build_target_context_artifact(
    *,
    match_id: str,
    identity_mapping: IdentityMapping,
    summary_payload: dict[str, object],
    season_info_payload: dict[str, object],
    profile_a_payload: dict[str, object],
    profile_b_payload: dict[str, object],
) -> TargetContextArtifact:
    event = parse_sportradar_prematch_event(
        summary_payload, expected_event_id=identity_mapping.sportradar_event_id
    )
    validate_mapping_against_event(identity_mapping, event)
    event_date = date.fromisoformat(identity_mapping.season_start_date)
    surface, level, draw_size = _season_info(
        season_info_payload,
        expected_season_id=identity_mapping.season_id,
        expected_competition_id=identity_mapping.competition_id,
    )
    sport_event, context = _summary_context(summary_payload)
    competitors = _qualified_competitors(sport_event)
    home = competitors["home"]
    away = competitors["away"]
    if _required_text(home, "id") != identity_mapping.player_a_sportradar_id:
        raise ValueError("target home competitor does not match identity mapping")
    if _required_text(away, "id") != identity_mapping.player_b_sportradar_id:
        raise ValueError("target away competitor does not match identity mapping")

    round_raw = context.get("round")
    round_name = None
    if round_raw is not None:
        round_obj = _as_dict(round_raw, field="sport_event_context.round")
        round_name = map_round(round_obj.get("name"))
    mode_raw = context.get("mode")
    best_of = None
    if mode_raw is not None:
        mode = _as_dict(mode_raw, field="sport_event_context.mode")
        best_of = _positive_int(mode.get("best_of"), field="mode.best_of")

    fields_a = _profile_fields(profile_a_payload, identity_mapping.player_a_sportradar_id, event_date)
    fields_b = _profile_fields(profile_b_payload, identity_mapping.player_b_sportradar_id, event_date)
    state = PreMatchState(
        match_id=_text(match_id),
        tour="ATP",
        event_date=event_date,
        source_order=0,
        tournament_id=identity_mapping.season_id,
        tournament_name=identity_mapping.competition_name,
        tournament_level=level,
        surface=surface,
        round=round_name,
        best_of=best_of,
        player_a_id=identity_mapping.player_a_canonical_id,
        player_b_id=identity_mapping.player_b_canonical_id,
        player_a_name=identity_mapping.player_a_market_name,
        player_b_name=identity_mapping.player_b_market_name,
        rank_a=None,
        rank_b=None,
        rank_points_a=None,
        rank_points_b=None,
        draw_size=draw_size,
        seed_a=_positive_int(home.get("seed"), field="home seed"),
        seed_b=_positive_int(away.get("seed"), field="away seed"),
        entry_a=None,
        entry_b=None,
        hand_a=fields_a["hand"],
        hand_b=fields_b["hand"],
        height_cm_a=fields_a["height_cm"],
        height_cm_b=fields_b["height_cm"],
        age_years_a=fields_a["age_years"],
        age_years_b=fields_b["age_years"],
        ioc_a=fields_a["ioc"],
        ioc_b=fields_b["ioc"],
    )
    if not state.match_id:
        raise ValueError("target match_id must be non-empty")
    unsigned: dict[str, object] = {
        "version": _TARGET_VERSION,
        "source_contract": "SPORTRADAR_TENNIS_V3_TARGET_V1",
        "match_id": state.match_id,
        "sportradar_event_id": identity_mapping.sportradar_event_id,
        "season_id": identity_mapping.season_id,
        "season_start_date": identity_mapping.season_start_date,
        "identity_mapping_sha256": identity_mapping.artifact_sha256,
        "summary_sha256": _sha(_canonical_json(summary_payload)),
        "season_info_sha256": _sha(_canonical_json(season_info_payload)),
        "profile_a_sha256": _sha(_canonical_json(profile_a_payload)),
        "profile_b_sha256": _sha(_canonical_json(profile_b_payload)),
        "pre_match": _pre_match_payload(state),
    }
    return TargetContextArtifact(**unsigned, artifact_sha256=_self_hash(unsigned))


def target_context_as_dict(artifact: TargetContextArtifact) -> dict[str, object]:
    return asdict(artifact)


def verify_target_context_artifact(
    payload: dict[str, object], *, identity_mapping: IdentityMapping
) -> TargetContextArtifact:
    if str(payload.get("artifact_sha256", "")) != _self_hash(payload):
        raise ValueError("target context artifact digest mismatch")
    artifact = TargetContextArtifact(**payload)
    if artifact.version != _TARGET_VERSION:
        raise ValueError("unexpected target context version")
    if artifact.identity_mapping_sha256 != identity_mapping.artifact_sha256:
        raise ValueError("target context identity mapping mismatch")
    if artifact.sportradar_event_id != identity_mapping.sportradar_event_id:
        raise ValueError("target context event mismatch")
    if artifact.season_id != identity_mapping.season_id:
        raise ValueError("target context season mismatch")
    if artifact.season_start_date != identity_mapping.season_start_date:
        raise ValueError("target context season start mismatch")
    state = _pre_match_from_payload(artifact.pre_match)
    if state.match_id != artifact.match_id or state.event_date.isoformat() != artifact.season_start_date:
        raise ValueError("target context pre-match identity/date mismatch")
    if state.player_a_id != identity_mapping.player_a_canonical_id:
        raise ValueError("target context canonical player A mismatch")
    if state.player_b_id != identity_mapping.player_b_canonical_id:
        raise ValueError("target context canonical player B mismatch")
    return artifact


def target_pre_match(artifact: TargetContextArtifact) -> PreMatchState:
    return _pre_match_from_payload(artifact.pre_match)


def _stats_side(raw: dict[str, object]) -> MatchStats | None:
    raise RuntimeError("_stats_side is not called directly")


def _summary_stats(summary: dict[str, object], match_id: str) -> MatchStats | None:
    statistics_raw = summary.get("statistics")
    if statistics_raw is None:
        return None
    statistics = _as_dict(statistics_raw, field="statistics")
    totals = _as_dict(statistics.get("totals"), field="statistics.totals")
    competitors = _qualified_competitors({"competitors": totals.get("competitors")})

    def side(qualifier: str) -> dict[str, object]:
        row = competitors[qualifier]
        return _as_dict(row.get("statistics"), field=f"{qualifier} statistics")

    home = side("home")
    away = side("away")

    def derived_service_points(values: dict[str, object], qualifier: str) -> int | None:
        won = _optional_nonnegative_int(values.get("service_points_won"), field=f"{qualifier} service_points_won")
        lost = _optional_nonnegative_int(values.get("service_points_lost"), field=f"{qualifier} service_points_lost")
        first = _optional_nonnegative_int(
            values.get("first_serve_points_won"), field=f"{qualifier} first_serve_points_won"
        )
        second = _optional_nonnegative_int(
            values.get("second_serve_points_won"), field=f"{qualifier} second_serve_points_won"
        )
        if won is not None and first is not None and second is not None and won != first + second:
            raise ValueError(f"{qualifier} service_points_won is inconsistent with serve components")
        if won is None or lost is None:
            return None
        return won + lost

    return MatchStats(
        match_id=match_id,
        aces_a=_optional_nonnegative_int(home.get("aces"), field="home aces"),
        aces_b=_optional_nonnegative_int(away.get("aces"), field="away aces"),
        double_faults_a=_optional_nonnegative_int(home.get("double_faults"), field="home double_faults"),
        double_faults_b=_optional_nonnegative_int(away.get("double_faults"), field="away double_faults"),
        service_points_a=derived_service_points(home, "home"),
        service_points_b=derived_service_points(away, "away"),
        first_serves_in_a=_optional_nonnegative_int(
            home.get("first_serve_successful"), field="home first_serve_successful"
        ),
        first_serves_in_b=_optional_nonnegative_int(
            away.get("first_serve_successful"), field="away first_serve_successful"
        ),
        first_serve_points_won_a=_optional_nonnegative_int(
            home.get("first_serve_points_won"), field="home first_serve_points_won"
        ),
        first_serve_points_won_b=_optional_nonnegative_int(
            away.get("first_serve_points_won"), field="away first_serve_points_won"
        ),
        second_serve_points_won_a=_optional_nonnegative_int(
            home.get("second_serve_points_won"), field="home second_serve_points_won"
        ),
        second_serve_points_won_b=_optional_nonnegative_int(
            away.get("second_serve_points_won"), field="away second_serve_points_won"
        ),
        duration_minutes=None,
    )


def _state_match_from_summary(
    summary: dict[str, object], *, crosswalk: dict[str, str], source_order: int
) -> HistoricalMatch:
    sport_event, context = _summary_context(summary)
    event_id = _required_text(sport_event, "id")
    category = _as_dict(context.get("category"), field="sport_event_context.category")
    if _required_text(category, "id") != _ATP_CATEGORY_ID:
        raise ValueError("NOT_ATP")
    competition = _as_dict(context.get("competition"), field="sport_event_context.competition")
    if _required_text(competition, "type").lower() != "singles":
        raise ValueError("NOT_SINGLES")
    competition_id = _required_text(competition, "id")
    season = _as_dict(context.get("season"), field="sport_event_context.season")
    season_id = _required_text(season, "id")
    if _required_text(season, "competition_id") != competition_id:
        raise ValueError("SEASON_COMPETITION_MISMATCH")
    event_date = date.fromisoformat(_required_text(season, "start_date"))

    status = _as_dict(summary.get("sport_event_status"), field="sport_event_status")
    status_name = _required_text(status, "status").lower()
    if status_name not in {"ended", "closed"}:
        raise ValueError("NOT_COMPLETED")
    competitors = _qualified_competitors(sport_event)
    home = competitors["home"]
    away = competitors["away"]
    home_sr = _required_text(home, "id")
    away_sr = _required_text(away, "id")
    home_id = _text(crosswalk.get(home_sr, ""))
    away_id = _text(crosswalk.get(away_sr, ""))
    if not home_id or not away_id:
        raise ValueError("UNRESOLVED_CANONICAL_ID")
    if home_id == away_id:
        raise ValueError("NONUNIQUE_CANONICAL_ID")
    winner = _required_text(status, "winner_id")
    if winner not in {home_sr, away_sr}:
        raise ValueError("WINNER_ID_MISMATCH")
    winning_reason = _normalized_enum(status.get("winning_reason"))
    if winning_reason and winning_reason not in {"walkover", "retirement", "defaulted"}:
        raise ValueError("UNRECOGNIZED_WINNING_REASON")

    round_raw = context.get("round")
    round_name = None
    if round_raw is not None:
        round_name = map_round(_as_dict(round_raw, field="round").get("name"))
    mode_raw = context.get("mode")
    best_of = None
    if mode_raw is not None:
        best_of = _positive_int(_as_dict(mode_raw, field="mode").get("best_of"), field="mode.best_of")

    pre = PreMatchState(
        match_id=event_id,
        tour="ATP",
        event_date=event_date,
        source_order=source_order,
        tournament_id=season_id,
        tournament_name=_required_text(competition, "name"),
        tournament_level=map_level(competition.get("level")),
        surface="Unknown",
        round=round_name,
        best_of=best_of,
        player_a_id=home_id,
        player_b_id=away_id,
        player_a_name=_required_text(home, "name"),
        player_b_name=_required_text(away, "name"),
        rank_a=None,
        rank_b=None,
        rank_points_a=None,
        rank_points_b=None,
        seed_a=_positive_int(home.get("seed"), field="home seed"),
        seed_b=_positive_int(away.get("seed"), field="away seed"),
        entry_a=None,
        entry_b=None,
        hand_a=None,
        hand_b=None,
        height_cm_a=None,
        height_cm_b=None,
        age_years_a=None,
        age_years_b=None,
        ioc_a=_text(home.get("country_code")) or None,
        ioc_b=_text(away.get("country_code")) or None,
    )
    excluded_finish = winning_reason in {"retirement", "defaulted"}
    outcome = MatchOutcome(
        match_id=event_id,
        a_won=winner == home_sr,
        score=None,
        retirement=excluded_finish,
        walkover=winning_reason == "walkover",
    )
    stats = None if outcome.retirement or outcome.walkover else _summary_stats(summary, event_id)
    return HistoricalMatch(pre_match=pre, outcome=outcome, stats=stats)


def _crosswalk_hash(crosswalk: dict[str, str]) -> str:
    normalized = {str(key): str(value) for key, value in sorted(crosswalk.items())}
    if any(not key.strip() or not value.strip() for key, value in normalized.items()):
        raise ValueError("state crosswalk contains blank ID")
    return _sha(_canonical_json(normalized))


def build_state_bundle(
    *, summaries: list[dict[str, object]], crosswalk: dict[str, str]
) -> SportradarStateBundle:
    crosswalk_sha = _crosswalk_hash(crosswalk)
    sorted_source = sorted(summaries, key=lambda item: _canonical_json(item))
    source_sha = _sha(_canonical_json(sorted_source))
    seen_events: set[str] = set()
    accepted: list[HistoricalMatch] = []
    exclusions: list[StateExclusion] = []
    for source_order, summary in enumerate(sorted_source):
        event_id = "UNKNOWN"
        try:
            sport_event = _as_dict(summary.get("sport_event"), field="sport_event")
            event_id = _required_text(sport_event, "id")
            if event_id in seen_events:
                raise ValueError("DUPLICATE_EVENT_ID")
            seen_events.add(event_id)
            accepted.append(
                _state_match_from_summary(
                    summary,
                    crosswalk=crosswalk,
                    source_order=source_order,
                )
            )
        except (TypeError, ValueError) as exc:
            reason = str(exc) or exc.__class__.__name__
            exclusions.append(StateExclusion(sport_event_id=event_id, reason=reason))
    accepted.sort(key=lambda match: (match.pre_match.event_date, match.match_id))
    rows = tuple(_historical_payload(match) for match in accepted)
    rows_sha = _sha(_canonical_json(rows))
    max_date = max((match.pre_match.event_date for match in accepted), default=None)
    exclusions.sort(key=lambda item: (item.sport_event_id, item.reason))
    unsigned: dict[str, object] = {
        "version": _STATE_VERSION,
        "source_contract": _STATE_SOURCE,
        "crosswalk_sha256": crosswalk_sha,
        "source_payload_sha256": source_sha,
        "parsed_rows_sha256": rows_sha,
        "source_count": len(summaries),
        "accepted_count": len(rows),
        "excluded_count": len(exclusions),
        "max_event_date": None if max_date is None else max_date.isoformat(),
        "rows": list(rows),
        "exclusions": [asdict(item) for item in exclusions],
    }
    return SportradarStateBundle(
        version=_STATE_VERSION,
        source_contract=_STATE_SOURCE,
        crosswalk_sha256=crosswalk_sha,
        source_payload_sha256=source_sha,
        parsed_rows_sha256=rows_sha,
        source_count=len(summaries),
        accepted_count=len(rows),
        excluded_count=len(exclusions),
        max_event_date=unsigned["max_event_date"],
        rows=rows,
        exclusions=tuple(exclusions),
        artifact_sha256=_self_hash(unsigned),
    )


def state_bundle_as_dict(bundle: SportradarStateBundle) -> dict[str, object]:
    return asdict(bundle)


def verify_state_bundle(
    payload: dict[str, object], *, crosswalk: dict[str, str]
) -> SportradarStateBundle:
    if str(payload.get("artifact_sha256", "")) != _self_hash(payload):
        raise ValueError("Sportradar state bundle digest mismatch")
    normalized = dict(payload)
    raw_rows = payload.get("rows", ())
    raw_exclusions = payload.get("exclusions", ())
    if not isinstance(raw_rows, (list, tuple)) or not isinstance(raw_exclusions, (list, tuple)):
        raise ValueError("state bundle rows/exclusions must be arrays")
    normalized["rows"] = tuple(_as_dict(item, field="state row") for item in raw_rows)
    normalized["exclusions"] = tuple(
        StateExclusion(**_as_dict(item, field="state exclusion")) for item in raw_exclusions
    )
    bundle = SportradarStateBundle(**normalized)
    if bundle.version != _STATE_VERSION or bundle.source_contract != _STATE_SOURCE:
        raise ValueError("unexpected Sportradar state bundle contract")
    if bundle.crosswalk_sha256 != _crosswalk_hash(crosswalk):
        raise ValueError("Sportradar state crosswalk hash mismatch")
    if bundle.parsed_rows_sha256 != _sha(_canonical_json(bundle.rows)):
        raise ValueError("Sportradar parsed-row hash mismatch")
    if bundle.accepted_count != len(bundle.rows):
        raise ValueError("Sportradar state accepted_count mismatch")
    if bundle.excluded_count != len(bundle.exclusions):
        raise ValueError("Sportradar state excluded_count mismatch")
    if bundle.source_count != bundle.accepted_count + bundle.excluded_count:
        raise ValueError("Sportradar state source accounting mismatch")
    history = [_historical_from_payload(row) for row in bundle.rows]
    expected_max = max((item.pre_match.event_date for item in history), default=None)
    expected_max_text = None if expected_max is None else expected_max.isoformat()
    if bundle.max_event_date != expected_max_text:
        raise ValueError("Sportradar state max_event_date mismatch")
    return bundle


def history_from_state_bundle(bundle: SportradarStateBundle) -> list[HistoricalMatch]:
    return [_historical_from_payload(row) for row in bundle.rows]
