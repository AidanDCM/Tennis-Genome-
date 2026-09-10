from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from tennis_genome.market.identity import MarketIdentityResolution
from tennis_genome.market.snapshot import MarketSnapshot

PROVIDER_KEY = "the_odds_api"


def canonical_payload_sha256(payload: object) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _parse_timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO timestamp")
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed


def _find_bookmaker(event: dict[str, Any], bookmaker_key: str) -> dict[str, Any]:
    bookmakers = event.get("bookmakers")
    if not isinstance(bookmakers, list):
        raise ValueError("event.bookmakers must be a list")
    matches = [
        bookmaker
        for bookmaker in bookmakers
        if isinstance(bookmaker, dict) and bookmaker.get("key") == bookmaker_key
    ]
    if len(matches) != 1:
        raise ValueError("bookmaker key must resolve to exactly one bookmaker")
    return matches[0]


def _find_h2h_market(bookmaker: dict[str, Any]) -> dict[str, Any]:
    markets = bookmaker.get("markets")
    if not isinstance(markets, list):
        raise ValueError("bookmaker.markets must be a list")
    matches = [
        market
        for market in markets
        if isinstance(market, dict) and market.get("key") == "h2h"
    ]
    if len(matches) != 1:
        raise ValueError("bookmaker must contain exactly one h2h market")
    return matches[0]


def _outcome_price(market: dict[str, Any], selection_name: str) -> float:
    outcomes = market.get("outcomes")
    if not isinstance(outcomes, list):
        raise ValueError("h2h market outcomes must be a list")
    matches = [
        outcome
        for outcome in outcomes
        if isinstance(outcome, dict) and outcome.get("name") == selection_name
    ]
    if len(matches) != 1:
        raise ValueError(f"selection {selection_name!r} must resolve to exactly one outcome")
    price = matches[0].get("price")
    if not isinstance(price, (int, float)):
        raise ValueError("outcome price must be numeric decimal odds")
    if float(price) <= 1.0:
        raise ValueError(
            "The Odds API adapter requires oddsFormat=decimal and prices greater than 1.0"
        )
    return float(price)


def parse_h2h_snapshot(
    *,
    event: dict[str, Any],
    bookmaker_key: str,
    collected_at: datetime,
    resolution: MarketIdentityResolution,
    raw_payload_sha256: str | None = None,
) -> MarketSnapshot:
    """Normalize one The Odds API bookmaker h2h quote after identity resolution."""

    if collected_at.tzinfo is None or collected_at.utcoffset() is None:
        raise ValueError("collected_at must be timezone-aware")
    event_id = event.get("id")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("event.id must be non-empty")
    if resolution.provider != PROVIDER_KEY:
        raise ValueError("identity resolution provider does not match The Odds API")
    if resolution.source_event_id != event_id:
        raise ValueError("identity resolution source_event_id does not match event.id")

    bookmaker = _find_bookmaker(event, bookmaker_key)
    market = _find_h2h_market(bookmaker)
    bookmaker_title = bookmaker.get("title") or bookmaker.get("key")
    if not isinstance(bookmaker_title, str) or not bookmaker_title.strip():
        raise ValueError("bookmaker title/key must be non-empty")

    observed_raw = market.get("last_update") or bookmaker.get("last_update")
    observed_at = _parse_timestamp(observed_raw, field="market/bookmaker last_update")
    commence_at = _parse_timestamp(event.get("commence_time"), field="commence_time")

    odds_a = _outcome_price(market, resolution.source_selection_a)
    odds_b = _outcome_price(market, resolution.source_selection_b)
    payload_hash = raw_payload_sha256 or canonical_payload_sha256(event)
    resolution_hash = resolution.resolution_hash()

    identity_material = {
        "provider": PROVIDER_KEY,
        "event_id": event_id,
        "bookmaker_key": bookmaker_key,
        "observed_at": observed_at.isoformat(),
        "selection_a": resolution.source_selection_a,
        "selection_b": resolution.source_selection_b,
        "odds_a": odds_a,
        "odds_b": odds_b,
        "identity_resolution_hash": resolution_hash,
    }
    snapshot_id = "market-" + canonical_payload_sha256(identity_material)[:24]
    source_market_id = market.get("sid")
    if source_market_id is not None:
        source_market_id = str(source_market_id)

    return MarketSnapshot(
        market_snapshot_id=snapshot_id,
        match_id=resolution.match_id,
        provider=PROVIDER_KEY,
        bookmaker=str(bookmaker.get("key") or bookmaker_title),
        market_type="h2h",
        collected_at=collected_at,
        observed_at=observed_at,
        commence_at=commence_at,
        player_a_id=resolution.player_a_id,
        player_b_id=resolution.player_b_id,
        selection_a_name=resolution.source_selection_a,
        selection_b_name=resolution.source_selection_b,
        decimal_odds_a=odds_a,
        decimal_odds_b=odds_b,
        source_event_id=event_id,
        source_market_id=source_market_id,
        source_payload_sha256=payload_hash,
        is_live=observed_at >= commence_at,
        is_suspended=False,
        identity_resolution_hash=resolution_hash,
    )
