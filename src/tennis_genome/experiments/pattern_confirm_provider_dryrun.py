from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from tennis_genome.experiments.pattern_confirm_live_identity import (
    SportradarPrematchEvent,
    parse_sportradar_prematch_event,
)

_EXPERIMENT_ID = "PATTERN-CONFIRM-PROVIDER-DRYRUN-001"
_VERSION = "pattern-confirm-provider-dryrun-v1"
_ODDS_PROVIDER = "THE_ODDS_API_V4_PINNACLE_V1"
_EVENT_PROVIDER = "SPORTRADAR_TENNIS_V3"
_ODDS_HOST = "https://api.the-odds-api.com"
_SPORTRADAR_HOST = "https://api.sportradar.com"
_BOOKMAKER = "pinnacle"
_MARKET = "h2h"
_MIN_STABILITY_SECONDS = 300
_MIN_DISTINCT_READY_EVENTS = 3
_MAX_QUOTE_STALENESS_SECONDS = 300
_MAX_START_DELTA = timedelta(hours=3)
_NAME_TOKEN = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class OddsCandidate:
    market_event_id: str
    sport_key: str
    sport_title: str
    scheduled_start: str
    player_a_name: str
    player_b_name: str
    bookmaker_last_update: str
    decimal_odds_a: float
    decimal_odds_b: float
    market_probability_a: float
    quote_staleness_seconds: float
    quote_fresh: bool


@dataclass(frozen=True)
class ProviderAlignment:
    market_event_id: str
    sportradar_event_id: str | None
    market_player_a_name: str
    market_player_b_name: str
    sportradar_player_a_id: str | None
    sportradar_player_b_id: str | None
    sportradar_player_a_name: str | None
    sportradar_player_b_name: str | None
    market_scheduled_start: str
    sportradar_scheduled_start: str | None
    competition_name: str | None
    status: str
    exclusion_reason: str | None


@dataclass(frozen=True)
class DryRunSnapshot:
    version: str
    captured_at: str
    queried_utc_dates: tuple[str, ...]
    tennis_sport_keys: tuple[str, ...]
    odds_transport_ok: bool
    sportradar_transport_ok: bool
    odds_raw_event_count: int
    pinnacle_valid_count: int
    sportradar_raw_summary_count: int
    sportradar_admissible_count: int
    aligned_count: int
    odds_candidates: tuple[OddsCandidate, ...]
    alignments: tuple[ProviderAlignment, ...]
    artifact_sha256: str


@dataclass(frozen=True)
class StableEvent:
    market_event_id: str
    sportradar_event_id: str
    player_a_name: str
    player_b_name: str
    sportradar_player_a_id: str
    sportradar_player_b_id: str


@dataclass(frozen=True)
class DryRunReport:
    experiment_id: str
    version: str
    outcome_blind: bool
    market_provider: str
    event_provider: str
    first_snapshot_sha256: str
    second_snapshot_sha256: str
    elapsed_seconds: float
    distinct_pinnacle_events: int
    distinct_aligned_events: int
    stable_event_count: int
    stable_events: tuple[StableEvent, ...]
    status: str
    reasons: tuple[str, ...]
    artifact_sha256: str


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


def _self_hash(payload: dict[str, object], field: str = "artifact_sha256") -> str:
    unsigned = dict(payload)
    unsigned.pop(field, None)
    return _sha256(_canonical_json(unsigned))


def _aware_time(value: object, *, field: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed


def _required_text(raw: dict[str, object], name: str) -> str:
    value = str(raw.get(name, "")).strip()
    if not value:
        raise ValueError(f"{name} must be non-empty")
    return value


def _as_dict(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _as_list(value: object, *, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    return value


def _normalized_name(value: object) -> str:
    return _NAME_TOKEN.sub(" ", str(value).strip().lower()).strip()


def _devig_probability(odds_a: float, odds_b: float) -> float:
    q_a = 1.0 / odds_a
    q_b = 1.0 / odds_b
    return q_a / (q_a + q_b)


def _decimal_price(value: object) -> float:
    price = float(value)
    if not math.isfinite(price) or price <= 1.0:
        raise ValueError("Pinnacle decimal price must be finite and greater than 1")
    return price


def discover_tennis_sport_keys(payload: object) -> tuple[str, ...]:
    sports = _as_list(payload, field="The Odds API sports response")
    keys: list[str] = []
    for raw in sports:
        item = _as_dict(raw, field="The Odds API sport")
        if item.get("active") is not True:
            continue
        if _required_text(item, "group").lower() != "tennis":
            continue
        keys.append(_required_text(item, "key"))
    return tuple(sorted(set(keys)))


def parse_pinnacle_candidates(
    payload: object,
    *,
    sport_key: str,
    captured_at: str,
) -> tuple[list[OddsCandidate], int]:
    events = _as_list(payload, field="The Odds API odds response")
    captured = _aware_time(captured_at, field="captured_at")
    candidates: list[OddsCandidate] = []
    for raw in events:
        event = _as_dict(raw, field="The Odds API event")
        if _required_text(event, "sport_key") != sport_key:
            raise ValueError("The Odds API event sport_key mismatch")
        event_id = _required_text(event, "id")
        scheduled = _aware_time(event.get("commence_time"), field="commence_time")
        player_a = _required_text(event, "home_team")
        player_b = _required_text(event, "away_team")
        if _normalized_name(player_a) == _normalized_name(player_b):
            raise ValueError("The Odds API competitors must be distinct")
        bookmakers = _as_list(event.get("bookmakers", []), field="bookmakers")
        pinnacle = [
            _as_dict(item, field="bookmaker")
            for item in bookmakers
            if isinstance(item, dict) and str(item.get("key", "")).strip() == _BOOKMAKER
        ]
        if not pinnacle:
            continue
        if len(pinnacle) != 1:
            raise ValueError("The Odds API event contains duplicate Pinnacle bookmaker blocks")
        book = pinnacle[0]
        last_update = _aware_time(book.get("last_update"), field="pinnacle.last_update")
        markets = [
            _as_dict(item, field="market")
            for item in _as_list(book.get("markets", []), field="pinnacle.markets")
            if isinstance(item, dict) and str(item.get("key", "")).strip() == _MARKET
        ]
        if len(markets) != 1:
            raise ValueError("Pinnacle candidate requires exactly one h2h market")
        outcomes = _as_list(markets[0].get("outcomes"), field="pinnacle.h2h.outcomes")
        if len(outcomes) != 2:
            raise ValueError("Pinnacle h2h market must have exactly two outcomes")
        by_name: dict[str, float] = {}
        for raw_outcome in outcomes:
            outcome = _as_dict(raw_outcome, field="pinnacle.h2h.outcome")
            name = _required_text(outcome, "name")
            normalized = _normalized_name(name)
            if normalized in by_name:
                raise ValueError("Pinnacle h2h outcome names must be distinct")
            by_name[normalized] = _decimal_price(outcome.get("price"))
        a_key = _normalized_name(player_a)
        b_key = _normalized_name(player_b)
        if set(by_name) != {a_key, b_key}:
            raise ValueError("Pinnacle h2h outcomes do not match event competitors")
        odds_a = by_name[a_key]
        odds_b = by_name[b_key]
        staleness = (captured - last_update).total_seconds()
        if staleness < -1.0:
            raise ValueError("Pinnacle last_update cannot materially postdate capture")
        candidates.append(
            OddsCandidate(
                market_event_id=event_id,
                sport_key=sport_key,
                sport_title=_required_text(event, "sport_title"),
                scheduled_start=scheduled.isoformat(),
                player_a_name=player_a,
                player_b_name=player_b,
                bookmaker_last_update=last_update.isoformat(),
                decimal_odds_a=odds_a,
                decimal_odds_b=odds_b,
                market_probability_a=_devig_probability(odds_a, odds_b),
                quote_staleness_seconds=max(staleness, 0.0),
                quote_fresh=staleness <= _MAX_QUOTE_STALENESS_SECONDS,
            )
        )
    candidates.sort(key=lambda item: (item.scheduled_start, item.market_event_id))
    return candidates, len(events)


def parse_sportradar_candidates(payload: object) -> tuple[list[SportradarPrematchEvent], int]:
    root = _as_dict(payload, field="Sportradar daily summaries response")
    summaries = _as_list(root.get("summaries"), field="summaries")
    events: list[SportradarPrematchEvent] = []
    for raw in summaries:
        summary = _as_dict(raw, field="summary")
        try:
            event = parse_sportradar_prematch_event(summary)
        except ValueError:
            continue
        events.append(event)
    events.sort(key=lambda item: (item.scheduled_start, item.sport_event_id))
    return events, len(summaries)


def _competition_overlap(market_title: str, sportradar_name: str) -> bool:
    left = _normalized_name(market_title)
    right = _normalized_name(sportradar_name)
    if not left or not right:
        return False
    if left in right or right in left:
        return True
    left_tokens = {token for token in left.split() if token not in {"tennis", "atp", "singles"}}
    right_tokens = {token for token in right.split() if token not in {"tennis", "atp", "singles", "men"}}
    return bool(left_tokens and right_tokens and left_tokens & right_tokens)


def align_candidate(
    market: OddsCandidate,
    sportradar_events: list[SportradarPrematchEvent],
) -> ProviderAlignment:
    market_names = {_normalized_name(market.player_a_name), _normalized_name(market.player_b_name)}
    market_start = _aware_time(market.scheduled_start, field="market scheduled_start")
    candidates: list[SportradarPrematchEvent] = []
    for event in sportradar_events:
        event_names = {
            _normalized_name(event.player_a_sportradar_name),
            _normalized_name(event.player_b_sportradar_name),
        }
        if event_names != market_names:
            continue
        event_start = _aware_time(event.scheduled_start, field="Sportradar scheduled_start")
        if abs(event_start - market_start) > _MAX_START_DELTA:
            continue
        if not _competition_overlap(market.sport_title, event.competition_name):
            continue
        candidates.append(event)
    if len(candidates) != 1:
        reason = "NO_EXACT_CONTEXT_MATCH" if not candidates else "AMBIGUOUS_EXACT_CONTEXT_MATCH"
        return ProviderAlignment(
            market_event_id=market.market_event_id,
            sportradar_event_id=None,
            market_player_a_name=market.player_a_name,
            market_player_b_name=market.player_b_name,
            sportradar_player_a_id=None,
            sportradar_player_b_id=None,
            sportradar_player_a_name=None,
            sportradar_player_b_name=None,
            market_scheduled_start=market.scheduled_start,
            sportradar_scheduled_start=None,
            competition_name=None,
            status="EXCLUDED",
            exclusion_reason=reason,
        )
    event = candidates[0]
    a_name = market.player_a_name
    b_name = market.player_b_name
    if _normalized_name(event.player_a_sportradar_name) == _normalized_name(market.player_b_name):
        a_name, b_name = b_name, a_name
    return ProviderAlignment(
        market_event_id=market.market_event_id,
        sportradar_event_id=event.sport_event_id,
        market_player_a_name=a_name,
        market_player_b_name=b_name,
        sportradar_player_a_id=event.player_a_sportradar_id,
        sportradar_player_b_id=event.player_b_sportradar_id,
        sportradar_player_a_name=event.player_a_sportradar_name,
        sportradar_player_b_name=event.player_b_sportradar_name,
        market_scheduled_start=market.scheduled_start,
        sportradar_scheduled_start=event.scheduled_start,
        competition_name=event.competition_name,
        status="ALIGNED",
        exclusion_reason=None,
    )


def build_snapshot(
    *,
    captured_at: str,
    queried_utc_dates: tuple[str, ...],
    sports_payload: object,
    odds_payloads: dict[str, object],
    sportradar_payloads: dict[str, object],
) -> DryRunSnapshot:
    _aware_time(captured_at, field="captured_at")
    sport_keys = discover_tennis_sport_keys(sports_payload)
    odds_candidates: list[OddsCandidate] = []
    raw_odds = 0
    for sport_key in sport_keys:
        payload = odds_payloads.get(sport_key, [])
        candidates, raw_count = parse_pinnacle_candidates(
            payload,
            sport_key=sport_key,
            captured_at=captured_at,
        )
        raw_odds += raw_count
        odds_candidates.extend(candidates)

    sportradar_events: list[SportradarPrematchEvent] = []
    raw_summaries = 0
    for query_date in queried_utc_dates:
        payload = sportradar_payloads.get(query_date, {"summaries": []})
        events, raw_count = parse_sportradar_candidates(payload)
        raw_summaries += raw_count
        sportradar_events.extend(events)

    alignments = [align_candidate(candidate, sportradar_events) for candidate in odds_candidates]
    unsigned: dict[str, object] = {
        "version": _VERSION,
        "captured_at": _aware_time(captured_at, field="captured_at").isoformat(),
        "queried_utc_dates": list(queried_utc_dates),
        "tennis_sport_keys": list(sport_keys),
        "odds_transport_ok": True,
        "sportradar_transport_ok": True,
        "odds_raw_event_count": raw_odds,
        "pinnacle_valid_count": len(odds_candidates),
        "sportradar_raw_summary_count": raw_summaries,
        "sportradar_admissible_count": len(sportradar_events),
        "aligned_count": sum(item.status == "ALIGNED" for item in alignments),
        "odds_candidates": [asdict(item) for item in odds_candidates],
        "alignments": [asdict(item) for item in alignments],
    }
    digest = _self_hash(unsigned)
    return DryRunSnapshot(
        version=_VERSION,
        captured_at=unsigned["captured_at"],
        queried_utc_dates=queried_utc_dates,
        tennis_sport_keys=sport_keys,
        odds_transport_ok=True,
        sportradar_transport_ok=True,
        odds_raw_event_count=raw_odds,
        pinnacle_valid_count=len(odds_candidates),
        sportradar_raw_summary_count=raw_summaries,
        sportradar_admissible_count=len(sportradar_events),
        aligned_count=sum(item.status == "ALIGNED" for item in alignments),
        odds_candidates=tuple(odds_candidates),
        alignments=tuple(alignments),
        artifact_sha256=digest,
    )


def snapshot_as_dict(snapshot: DryRunSnapshot) -> dict[str, object]:
    return asdict(snapshot)


def verify_snapshot(payload: dict[str, object]) -> DryRunSnapshot:
    stored = str(payload.get("artifact_sha256", ""))
    if not stored or _self_hash(payload) != stored:
        raise ValueError("provider dry-run snapshot digest mismatch")
    normalized = dict(payload)
    normalized["queried_utc_dates"] = tuple(payload.get("queried_utc_dates", ()))
    normalized["tennis_sport_keys"] = tuple(payload.get("tennis_sport_keys", ()))
    normalized["odds_candidates"] = tuple(
        OddsCandidate(**item)
        for item in _as_list(payload.get("odds_candidates", []), field="odds_candidates")
        if isinstance(item, dict)
    )
    normalized["alignments"] = tuple(
        ProviderAlignment(**item)
        for item in _as_list(payload.get("alignments", []), field="alignments")
        if isinstance(item, dict)
    )
    snapshot = DryRunSnapshot(**normalized)
    if snapshot.version != _VERSION:
        raise ValueError("unexpected provider dry-run snapshot version")
    _aware_time(snapshot.captured_at, field="captured_at")
    return snapshot


def compare_snapshots(first: DryRunSnapshot, second: DryRunSnapshot) -> DryRunReport:
    first_time = _aware_time(first.captured_at, field="first captured_at")
    second_time = _aware_time(second.captured_at, field="second captured_at")
    elapsed = (second_time - first_time).total_seconds()
    if elapsed < 0:
        raise ValueError("provider dry-run snapshots are out of order")

    def aligned_map(snapshot: DryRunSnapshot) -> dict[str, ProviderAlignment]:
        return {
            item.market_event_id: item
            for item in snapshot.alignments
            if item.status == "ALIGNED" and item.sportradar_event_id is not None
        }

    first_aligned = aligned_map(first)
    second_aligned = aligned_map(second)
    stable: list[StableEvent] = []
    for event_id in sorted(set(first_aligned) & set(second_aligned)):
        a = first_aligned[event_id]
        b = second_aligned[event_id]
        if (
            a.sportradar_event_id == b.sportradar_event_id
            and a.market_player_a_name == b.market_player_a_name
            and a.market_player_b_name == b.market_player_b_name
            and a.sportradar_player_a_id == b.sportradar_player_a_id
            and a.sportradar_player_b_id == b.sportradar_player_b_id
            and a.sportradar_player_a_id is not None
            and a.sportradar_player_b_id is not None
            and a.sportradar_event_id is not None
        ):
            stable.append(
                StableEvent(
                    market_event_id=event_id,
                    sportradar_event_id=a.sportradar_event_id,
                    player_a_name=a.market_player_a_name,
                    player_b_name=a.market_player_b_name,
                    sportradar_player_a_id=a.sportradar_player_a_id,
                    sportradar_player_b_id=a.sportradar_player_b_id,
                )
            )

    distinct_pinnacle = len(
        {item.market_event_id for item in (*first.odds_candidates, *second.odds_candidates)}
    )
    distinct_aligned = len(set(first_aligned) | set(second_aligned))
    reasons: list[str] = []
    if not first.tennis_sport_keys or not second.tennis_sport_keys:
        reasons.append("NO_ACTIVE_TENNIS_SPORT_KEYS")
    if elapsed < _MIN_STABILITY_SECONDS:
        reasons.append("SNAPSHOTS_LESS_THAN_FIVE_MINUTES_APART")
    fresh_event_ids = {
        item.market_event_id
        for item in (*first.odds_candidates, *second.odds_candidates)
        if item.quote_fresh
    }
    stable_fresh = [item for item in stable if item.market_event_id in fresh_event_ids]
    if distinct_pinnacle < _MIN_DISTINCT_READY_EVENTS:
        reasons.append("FEWER_THAN_THREE_PINNACLE_EVENTS")
    if len(stable_fresh) < _MIN_DISTINCT_READY_EVENTS:
        reasons.append("FEWER_THAN_THREE_STABLE_FRESH_ALIGNED_EVENTS")

    if any(
        reason in {"NO_ACTIVE_TENNIS_SPORT_KEYS", "SNAPSHOTS_LESS_THAN_FIVE_MINUTES_APART"}
        for reason in reasons
    ):
        status = "FAIL_CLOSED"
    elif distinct_pinnacle < _MIN_DISTINCT_READY_EVENTS:
        status = "INSUFFICIENT_LIVE_SAMPLE"
    elif len(stable_fresh) < _MIN_DISTINCT_READY_EVENTS:
        status = "FAIL_CLOSED"
    else:
        status = "TRANSPORT_COMPATIBLE"

    unsigned: dict[str, object] = {
        "experiment_id": _EXPERIMENT_ID,
        "version": _VERSION,
        "outcome_blind": True,
        "market_provider": _ODDS_PROVIDER,
        "event_provider": _EVENT_PROVIDER,
        "first_snapshot_sha256": first.artifact_sha256,
        "second_snapshot_sha256": second.artifact_sha256,
        "elapsed_seconds": elapsed,
        "distinct_pinnacle_events": distinct_pinnacle,
        "distinct_aligned_events": distinct_aligned,
        "stable_event_count": len(stable_fresh),
        "stable_events": [asdict(item) for item in stable_fresh],
        "status": status,
        "reasons": reasons,
    }
    digest = _self_hash(unsigned)
    return DryRunReport(
        experiment_id=_EXPERIMENT_ID,
        version=_VERSION,
        outcome_blind=True,
        market_provider=_ODDS_PROVIDER,
        event_provider=_EVENT_PROVIDER,
        first_snapshot_sha256=first.artifact_sha256,
        second_snapshot_sha256=second.artifact_sha256,
        elapsed_seconds=elapsed,
        distinct_pinnacle_events=distinct_pinnacle,
        distinct_aligned_events=distinct_aligned,
        stable_event_count=len(stable_fresh),
        stable_events=tuple(stable_fresh),
        status=status,
        reasons=tuple(reasons),
        artifact_sha256=digest,
    )


def report_as_dict(report: DryRunReport) -> dict[str, object]:
    return asdict(report)


def _http_json(url: str, *, headers: dict[str, str] | None = None) -> object:
    request = Request(url, headers=headers or {})
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed HTTPS provider hosts
            raw = response.read()
    except Exception as exc:
        safe_url = url.split("?", 1)[0]
        raise RuntimeError(f"provider request failed: {safe_url}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("provider returned non-JSON response") from exc


def _future_utc_dates(now: datetime) -> tuple[str, str]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    utc_day = now.astimezone(UTC).date()
    return ((utc_day + timedelta(days=1)).isoformat(), (utc_day + timedelta(days=2)).isoformat())


def capture_live_snapshot(
    *,
    odds_api_key: str,
    sportradar_api_key: str,
    sportradar_access_level: str,
    now: datetime | None = None,
    get_json: Callable[..., object] = _http_json,
) -> DryRunSnapshot:
    if not odds_api_key.strip() or not sportradar_api_key.strip():
        raise ValueError("provider API keys must be non-empty")
    if sportradar_access_level not in {"trial", "production"}:
        raise ValueError("Sportradar access level must be trial or production")
    captured = now or datetime.now(UTC)
    captured_at = captured.astimezone(UTC).isoformat()
    sports_url = f"{_ODDS_HOST}/v4/sports/?{urlencode({'apiKey': odds_api_key})}"
    sports_payload = get_json(sports_url)
    keys = discover_tennis_sport_keys(sports_payload)
    odds_payloads: dict[str, object] = {}
    for sport_key in keys:
        query = urlencode(
            {
                "apiKey": odds_api_key,
                "bookmakers": _BOOKMAKER,
                "markets": _MARKET,
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            }
        )
        odds_payloads[sport_key] = get_json(
            f"{_ODDS_HOST}/v4/sports/{sport_key}/odds/?{query}"
        )

    queried_dates = _future_utc_dates(captured)
    sportradar_payloads: dict[str, object] = {}
    headers = {"x-api-key": sportradar_api_key}
    for query_date in queried_dates:
        url = (
            f"{_SPORTRADAR_HOST}/tennis/{sportradar_access_level}/v3/en/"
            f"schedules/{query_date}/summaries.json"
        )
        sportradar_payloads[query_date] = get_json(url, headers=headers)
    return build_snapshot(
        captured_at=captured_at,
        queried_utc_dates=queried_dates,
        sports_payload=sports_payload,
        odds_payloads=odds_payloads,
        sportradar_payloads=sportradar_payloads,
    )


def run_live_dryrun(
    *,
    odds_api_key: str,
    sportradar_api_key: str,
    sportradar_access_level: str,
    delay_seconds: int = _MIN_STABILITY_SECONDS,
) -> tuple[DryRunSnapshot, DryRunSnapshot, DryRunReport]:
    if delay_seconds < _MIN_STABILITY_SECONDS:
        raise ValueError("live readiness snapshots must be at least five minutes apart")
    first = capture_live_snapshot(
        odds_api_key=odds_api_key,
        sportradar_api_key=sportradar_api_key,
        sportradar_access_level=sportradar_access_level,
    )
    time.sleep(delay_seconds)
    second = capture_live_snapshot(
        odds_api_key=odds_api_key,
        sportradar_api_key=sportradar_api_key,
        sportradar_access_level=sportradar_access_level,
    )
    return first, second, compare_snapshots(first, second)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Outcome-blind PATTERN-CONFIRM provider dry-run")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--delay-seconds", type=int, default=_MIN_STABILITY_SECONDS)
    parser.add_argument(
        "--sportradar-access-level",
        default=os.environ.get("SPORTRADAR_ACCESS_LEVEL", "trial"),
        choices=("trial", "production"),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    odds_key = os.environ.get("THE_ODDS_API_KEY", "")
    sportradar_key = os.environ.get("SPORTRADAR_API_KEY", "")
    first, second, report = run_live_dryrun(
        odds_api_key=odds_key,
        sportradar_api_key=sportradar_key,
        sportradar_access_level=args.sportradar_access_level,
        delay_seconds=args.delay_seconds,
    )
    _write_json(args.output_dir / "snapshot_1.json", snapshot_as_dict(first))
    _write_json(args.output_dir / "snapshot_2.json", snapshot_as_dict(second))
    _write_json(args.output_dir / "provider_dryrun_report.json", report_as_dict(report))
    print(json.dumps(report_as_dict(report), indent=2, sort_keys=True, allow_nan=False))
    if report.status == "FAIL_CLOSED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
