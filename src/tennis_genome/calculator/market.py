from __future__ import annotations

import hashlib
import json
from datetime import datetime

from tennis_genome.market.comparison import MarketComparison, compare_prediction_to_market
from tennis_genome.market.snapshot import MarketSnapshot

from .types import MatchupCalculation


def _sha256_json(payload: dict[str, object]) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def compare_manual_decimal_odds(
    *,
    comparison_id: str,
    market_snapshot_id: str,
    created_at: datetime,
    observed_at: datetime,
    calculation: MatchupCalculation,
    decimal_odds_a: float,
    decimal_odds_b: float,
    selection_a_name: str,
    selection_b_name: str,
    bookmaker: str = "MANUAL",
    commence_at: datetime | None = None,
) -> MarketComparison:
    """Compare manual pre-match prices after independent inference is complete.

    The adapter consumes the sealed ``MatchupCalculation`` only. It has no path
    back into ``MatchupCalculator.calculate`` and therefore cannot alter the
    independent probability or its A/B orientation.
    """
    prediction = calculation.prediction
    payload = {
        "match_id": prediction.match_id,
        "observed_at": observed_at.isoformat(),
        "player_a_id": calculation.player_a_id,
        "player_b_id": calculation.player_b_id,
        "decimal_odds_a": float(decimal_odds_a),
        "decimal_odds_b": float(decimal_odds_b),
        "selection_a_name": selection_a_name,
        "selection_b_name": selection_b_name,
        "bookmaker": bookmaker,
    }
    identity_payload = {
        "match_id": prediction.match_id,
        "player_a_id": calculation.player_a_id,
        "player_b_id": calculation.player_b_id,
    }
    market = MarketSnapshot(
        market_snapshot_id=market_snapshot_id,
        match_id=prediction.match_id,
        provider="manual_input",
        bookmaker=bookmaker,
        market_type="h2h",
        collected_at=created_at,
        observed_at=observed_at,
        player_a_id=calculation.player_a_id,
        player_b_id=calculation.player_b_id,
        selection_a_name=selection_a_name,
        selection_b_name=selection_b_name,
        decimal_odds_a=decimal_odds_a,
        decimal_odds_b=decimal_odds_b,
        source_event_id=f"manual:{prediction.match_id}",
        source_payload_sha256=_sha256_json(payload),
        identity_resolution_hash=_sha256_json(identity_payload),
        commence_at=commence_at,
        is_live=False,
        is_suspended=False,
    )
    return compare_prediction_to_market(
        comparison_id=comparison_id,
        created_at=created_at,
        prediction=prediction,
        market=market,
    )
