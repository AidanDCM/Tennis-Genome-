from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

_MARKET_PROVIDER = "THE_ODDS_API_V4_PINNACLE_V1"
_EVENT_PROVIDER = "SPORTRADAR_TENNIS_V3"
_VERSION = "pattern-confirm-identity-v2"
_ATP_CATEGORY_ID = "sr:category:3"
_ALLOWED_METHODS = {
    "EXPLICIT_CROSSWALK",
    "EXACT_CONTEXT_UNIQUE",
    "MANUAL_PREMATCH",
}
_NON_PREMATCH_STATUSES = {
    "live",
    "ended",
    "closed",
    "cancelled",
    "canceled",
    "abandoned",
    "interrupted",
    "suspended",
    "postponed",
}
_NAME_TOKEN = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class IdentityMapping:
    version: str
    market_provider: str
    event_provider: str
    market_event_id: str
    sportradar_event_id: str
    player_a_market_name: str
    player_b_market_name: str
    player_a_sportradar_id: str
    player_b_sportradar_id: str
    player_a_canonical_id: str
    player_b_canonical_id: str
    player_a_sportradar_name: str
    player_b_sportradar_name: str
    competition_id: str
    competition_name: str
    season_id: str
    season_start_date: str
    scheduled_start: str
    method: str
    created_at: str
    artifact_sha256: str


@dataclass(frozen=True)
class SportradarPrematchEvent:
    sport_event_id: str
    scheduled_start: str
    category_id: str
    competition_id: str
    competition_name: str
    competition_type: str
    season_id: str
    season_start_date: str
    player_a_sportradar_id: str
    player_b_sportradar_id: str
    player_a_sportradar_name: str
    player_b_sportradar_name: str
    provider_status: str


@dataclass(frozen=True)
class SportradarActualStart:
    sport_event_id: str
    actual_start: str | None
    source: str
    exclusion_reason: str | None
    timeline_sha256: str


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _self_hash(payload: dict[str, object]) -> str:
    unsigned = dict(payload)
    unsigned.pop("artifact_sha256", None)
    return _sha256(_canonical_json(unsigned))


def _required_text(raw: dict[str, object], name: str) -> str:
    value = str(raw.get(name, "")).strip()
    if not value:
        raise ValueError(f"{name} must be non-empty")
    return value


def _aware_time(value: object, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed


def _normalized_name(value: object) -> str:
    text = str(value).strip().lower()
    return _NAME_TOKEN.sub(" ", text).strip()


def _iso_date(value: object, *, field: str) -> str:
    from datetime import date

    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO date YYYY-MM-DD") from exc


def _as_dict(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _as_list(value: object, *, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    return value


def _event_from_summary(payload: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    sport_event = _as_dict(payload.get("sport_event"), field="sport_event")
    status_raw = payload.get("sport_event_status", {})
    status = _as_dict(status_raw, field="sport_event_status")
    return sport_event, status


def _qualifier_map(competitors: Iterable[object]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for item in competitors:
        competitor = _as_dict(item, field="competitor")
        qualifier = _required_text(competitor, "qualifier").lower()
        if qualifier not in {"home", "away"}:
            raise ValueError("Sportradar competitor qualifier must be home or away")
        if qualifier in result:
            raise ValueError("Sportradar competitors contain duplicate qualifier")
        result[qualifier] = competitor
    if set(result) != {"home", "away"}:
        raise ValueError("Sportradar event must contain exactly home and away competitors")
    return result


def parse_sportradar_prematch_event(
    payload: dict[str, object],
    *,
    expected_event_id: str | None = None,
) -> SportradarPrematchEvent:
    sport_event, status = _event_from_summary(payload)
    event_id = _required_text(sport_event, "id")
    if expected_event_id is not None and event_id != expected_event_id:
        raise ValueError("Sportradar sport-event ID mismatch")
    if sport_event.get("start_time_confirmed") is not True:
        raise ValueError("Sportradar start_time_confirmed must be true")
    scheduled_start = _aware_time(sport_event.get("start_time"), field="sport_event.start_time")

    context = _as_dict(sport_event.get("sport_event_context"), field="sport_event_context")
    category = _as_dict(context.get("category"), field="sport_event_context.category")
    if _required_text(category, "id") != _ATP_CATEGORY_ID:
        raise ValueError("Sportradar event is not ATP category sr:category:3")
    if _required_text(category, "name").upper() != "ATP":
        raise ValueError("Sportradar ATP category name mismatch")

    competition = _as_dict(context.get("competition"), field="sport_event_context.competition")
    competition_type = _required_text(competition, "type").lower()
    if competition_type != "singles":
        raise ValueError("PATTERN-CONFIRM-001 requires a singles competition")
    competition_id = _required_text(competition, "id")
    competition_name = _required_text(competition, "name")
    season = _as_dict(context.get("season"), field="sport_event_context.season")
    season_id = _required_text(season, "id")
    season_start_date = _iso_date(
        season.get("start_date"), field="sport_event_context.season.start_date"
    )
    season_competition_id = _required_text(season, "competition_id")
    if season_competition_id != competition_id:
        raise ValueError("Sportradar season competition_id does not match competition")

    provider_status = _required_text(status, "status").lower()
    if provider_status in _NON_PREMATCH_STATUSES:
        raise ValueError("Sportradar event is not in an admissible pre-match state")
    if provider_status not in {"not_started", "scheduled"}:
        raise ValueError("unrecognized Sportradar pre-match status")

    qualifiers = _qualifier_map(
        _as_list(sport_event.get("competitors"), field="sport_event.competitors")
    )
    home = qualifiers["home"]
    away = qualifiers["away"]
    home_id = _required_text(home, "id")
    away_id = _required_text(away, "id")
    if home_id == away_id:
        raise ValueError("Sportradar competitor IDs must differ")
    if bool(home.get("virtual", False)) or bool(away.get("virtual", False)):
        raise ValueError("virtual/TBD competitors are not confirmatory-eligible")

    return SportradarPrematchEvent(
        sport_event_id=event_id,
        scheduled_start=scheduled_start.isoformat(),
        category_id=_ATP_CATEGORY_ID,
        competition_id=competition_id,
        competition_name=competition_name,
        competition_type=competition_type,
        season_id=season_id,
        season_start_date=season_start_date,
        player_a_sportradar_id=home_id,
        player_b_sportradar_id=away_id,
        player_a_sportradar_name=_required_text(home, "name"),
        player_b_sportradar_name=_required_text(away, "name"),
        provider_status=provider_status,
    )


def build_identity_mapping(
    *,
    market_event_id: str,
    market_player_a_name: str,
    market_player_b_name: str,
    player_a_canonical_id: str,
    player_b_canonical_id: str,
    sportradar_event: SportradarPrematchEvent,
    method: str,
    created_at: str,
) -> IdentityMapping:
    method = str(method).strip().upper()
    if method not in _ALLOWED_METHODS:
        raise ValueError("identity mapping method is not frozen/allowed")
    created = _aware_time(created_at, field="created_at")
    scheduled = _aware_time(sportradar_event.scheduled_start, field="scheduled_start")
    if created >= scheduled:
        raise ValueError("identity mapping must be created before scheduled start")

    market_event_id = str(market_event_id).strip()
    market_a = str(market_player_a_name).strip()
    market_b = str(market_player_b_name).strip()
    canonical_a = str(player_a_canonical_id).strip()
    canonical_b = str(player_b_canonical_id).strip()
    if not all((market_event_id, market_a, market_b, canonical_a, canonical_b)):
        raise ValueError("identity mapping fields must be non-empty")
    if canonical_a == canonical_b:
        raise ValueError("canonical player IDs must differ")

    unsigned: dict[str, object] = {
        "version": _VERSION,
        "market_provider": _MARKET_PROVIDER,
        "event_provider": _EVENT_PROVIDER,
        "market_event_id": market_event_id,
        "sportradar_event_id": sportradar_event.sport_event_id,
        "player_a_market_name": market_a,
        "player_b_market_name": market_b,
        "player_a_sportradar_id": sportradar_event.player_a_sportradar_id,
        "player_b_sportradar_id": sportradar_event.player_b_sportradar_id,
        "player_a_canonical_id": canonical_a,
        "player_b_canonical_id": canonical_b,
        "player_a_sportradar_name": sportradar_event.player_a_sportradar_name,
        "player_b_sportradar_name": sportradar_event.player_b_sportradar_name,
        "competition_id": sportradar_event.competition_id,
        "competition_name": sportradar_event.competition_name,
        "season_id": sportradar_event.season_id,
        "season_start_date": sportradar_event.season_start_date,
        "scheduled_start": sportradar_event.scheduled_start,
        "method": method,
        "created_at": created.isoformat(),
    }
    return IdentityMapping(**unsigned, artifact_sha256=_self_hash(unsigned))


def verify_identity_mapping(payload: dict[str, object]) -> IdentityMapping:
    stored = str(payload.get("artifact_sha256", ""))
    if not stored or stored != _self_hash(payload):
        raise ValueError("identity mapping digest mismatch")
    mapping = IdentityMapping(**payload)
    if mapping.version != _VERSION:
        raise ValueError("unexpected identity mapping version")
    if mapping.market_provider != _MARKET_PROVIDER:
        raise ValueError("unexpected market provider in identity mapping")
    if mapping.event_provider != _EVENT_PROVIDER:
        raise ValueError("unexpected event provider in identity mapping")
    if mapping.method not in _ALLOWED_METHODS:
        raise ValueError("identity mapping method is not allowed")
    if mapping.player_a_sportradar_id == mapping.player_b_sportradar_id:
        raise ValueError("identity mapping Sportradar competitor IDs must differ")
    if mapping.player_a_canonical_id == mapping.player_b_canonical_id:
        raise ValueError("identity mapping canonical player IDs must differ")
    _aware_time(mapping.created_at, field="created_at")
    _iso_date(mapping.season_start_date, field="season_start_date")
    if not mapping.season_id.strip():
        raise ValueError("identity mapping season_id must be non-empty")
    scheduled = _aware_time(mapping.scheduled_start, field="scheduled_start")
    if _aware_time(mapping.created_at, field="created_at") >= scheduled:
        raise ValueError("identity mapping was not created pre-match")
    return mapping


def validate_mapping_against_event(
    mapping: IdentityMapping,
    event: SportradarPrematchEvent,
) -> None:
    if mapping.sportradar_event_id != event.sport_event_id:
        raise ValueError("identity mapping references a different Sportradar event")
    if mapping.player_a_sportradar_id != event.player_a_sportradar_id:
        raise ValueError("identity mapping player A does not match Sportradar home competitor")
    if mapping.player_b_sportradar_id != event.player_b_sportradar_id:
        raise ValueError("identity mapping player B does not match Sportradar away competitor")
    if mapping.competition_id != event.competition_id:
        raise ValueError("identity mapping competition does not match Sportradar event")
    if mapping.season_id != event.season_id:
        raise ValueError("identity mapping season does not match Sportradar event")
    if mapping.season_start_date != event.season_start_date:
        raise ValueError("identity mapping season start does not match Sportradar event")
    if mapping.scheduled_start != event.scheduled_start:
        raise ValueError("identity mapping scheduled start does not match Sportradar event")


def resolve_exact_context_unique(
    *,
    market_event_id: str,
    market_player_a_name: str,
    market_player_b_name: str,
    player_a_canonical_id: str,
    player_b_canonical_id: str,
    market_scheduled_start: str,
    market_competition_name: str,
    candidate_payloads: Iterable[dict[str, object]],
    created_at: str,
    max_start_delta: timedelta = timedelta(hours=3),
) -> IdentityMapping:
    market_names = {
        _normalized_name(market_player_a_name),
        _normalized_name(market_player_b_name),
    }
    if len(market_names) != 2 or "" in market_names:
        raise ValueError("market competitor names must be distinct and non-empty")
    market_start = _aware_time(market_scheduled_start, field="market_scheduled_start")
    competition_key = _normalized_name(market_competition_name)
    if not competition_key:
        raise ValueError("market competition name must be non-empty")

    candidates: list[SportradarPrematchEvent] = []
    for payload in candidate_payloads:
        try:
            event = parse_sportradar_prematch_event(payload)
        except ValueError:
            continue
        event_names = {
            _normalized_name(event.player_a_sportradar_name),
            _normalized_name(event.player_b_sportradar_name),
        }
        event_start = _aware_time(event.scheduled_start, field="candidate scheduled_start")
        if event_names != market_names:
            continue
        if abs(event_start - market_start) > max_start_delta:
            continue
        event_competition = _normalized_name(event.competition_name)
        if competition_key not in event_competition and event_competition not in competition_key:
            continue
        candidates.append(event)

    if len(candidates) != 1:
        raise ValueError(
            "exact-context identity resolution requires exactly one candidate; "
            f"found {len(candidates)}"
        )
    event = candidates[0]
    if _normalized_name(event.player_a_sportradar_name) == _normalized_name(market_player_b_name):
        market_player_a_name, market_player_b_name = market_player_b_name, market_player_a_name
        player_a_canonical_id, player_b_canonical_id = (
            player_b_canonical_id,
            player_a_canonical_id,
        )
    return build_identity_mapping(
        market_event_id=market_event_id,
        market_player_a_name=market_player_a_name,
        market_player_b_name=market_player_b_name,
        player_a_canonical_id=player_a_canonical_id,
        player_b_canonical_id=player_b_canonical_id,
        sportradar_event=event,
        method="EXACT_CONTEXT_UNIQUE",
        created_at=created_at,
    )


def parse_sportradar_actual_start(
    payload: dict[str, object],
    *,
    expected_event_id: str,
) -> SportradarActualStart:
    sport_event = _as_dict(payload.get("sport_event"), field="sport_event")
    event_id = _required_text(sport_event, "id")
    if event_id != expected_event_id:
        raise ValueError("Sportradar timeline event ID mismatch")
    timeline = _as_list(payload.get("timeline"), field="timeline")
    starts: list[datetime] = []
    for raw in timeline:
        event = _as_dict(raw, field="timeline event")
        if str(event.get("type", "")).strip() != "match_started":
            continue
        starts.append(_aware_time(event.get("time"), field="timeline.match_started.time"))
    timeline_sha = _sha256(_canonical_json(payload))
    if not starts:
        return SportradarActualStart(
            sport_event_id=event_id,
            actual_start=None,
            source="SPORTRADAR_TIMELINE_MATCH_STARTED_V1",
            exclusion_reason="ACTUAL_START_UNVERIFIED",
            timeline_sha256=timeline_sha,
        )
    actual = min(starts)
    return SportradarActualStart(
        sport_event_id=event_id,
        actual_start=actual.isoformat(),
        source="SPORTRADAR_TIMELINE_MATCH_STARTED_V1",
        exclusion_reason=None,
        timeline_sha256=timeline_sha,
    )


def identity_mapping_as_dict(mapping: IdentityMapping) -> dict[str, object]:
    return asdict(mapping)
