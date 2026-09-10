from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

from tennis_genome.independent.prediction import IndependentPrediction
from tennis_genome.market.odds import (
    edge_percentage_points,
    expected_value_per_unit,
    implied_probability_from_decimal,
    proportional_novig_two_way,
)
from tennis_genome.market.snapshot import MarketSnapshot

NoVigMethod = Literal["proportional_two_way_v1"]


@dataclass(frozen=True)
class MarketComparison:
    """Derived market comparison; contains no staking or realized outcome."""

    comparison_id: str
    created_at: datetime
    prediction_id: str
    market_snapshot_id: str
    match_id: str
    model_version: str
    architecture_hash: str
    novig_method: NoVigMethod
    raw_implied_p_a: float
    raw_implied_p_b: float
    book_margin: float
    novig_p_a: float
    novig_p_b: float
    model_p_a: float
    model_p_b: float
    edge_a_pp: float
    edge_b_pp: float
    ev_a_per_unit: float
    ev_b_per_unit: float
    market_observed_at: datetime
    decision_eligible: bool
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["created_at"] = self.created_at.isoformat()
        payload["market_observed_at"] = self.market_observed_at.isoformat()
        return payload


def compare_prediction_to_market(
    *,
    comparison_id: str,
    created_at: datetime,
    prediction: IndependentPrediction,
    market: MarketSnapshot,
) -> MarketComparison:
    if not comparison_id:
        raise ValueError("comparison_id must be non-empty")
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    if prediction.match_id != market.match_id:
        raise ValueError("prediction and market snapshot must have the same match_id")
    if market.market_type != "h2h":
        raise ValueError("MarketComparison v1 supports h2h only")
    if market.is_live:
        raise ValueError("MarketComparison v1 does not accept live markets")
    if created_at < prediction.created_at or created_at < market.collected_at:
        raise ValueError("comparison cannot predate its prediction or market snapshot")

    raw_a = implied_probability_from_decimal(market.decimal_odds_a)
    raw_b = implied_probability_from_decimal(market.decimal_odds_b)
    novig_a, novig_b = proportional_novig_two_way(
        market.decimal_odds_a,
        market.decimal_odds_b,
    )
    margin = raw_a + raw_b - 1.0
    edge_a = edge_percentage_points(
        p_model=prediction.p_player_a,
        p_market_novig=novig_a,
    )
    edge_b = edge_percentage_points(
        p_model=prediction.p_player_b,
        p_market_novig=novig_b,
    )
    ev_a = expected_value_per_unit(
        p_win=prediction.p_player_a,
        decimal_odds=market.decimal_odds_a,
    )
    ev_b = expected_value_per_unit(
        p_win=prediction.p_player_b,
        decimal_odds=market.decimal_odds_b,
    )

    reasons: list[str] = []
    if market.is_suspended:
        reasons.append("MARKET_SUSPENDED")
    if market.observed_at < prediction.prediction_cutoff_at:
        reasons.append("MARKET_PRECEDES_MODEL_CUTOFF")
    if market.commence_at is not None and created_at > market.commence_at:
        reasons.append("DECISION_AFTER_COMMENCE")

    eligible = not reasons
    return MarketComparison(
        comparison_id=comparison_id,
        created_at=created_at,
        prediction_id=prediction.prediction_id,
        market_snapshot_id=market.market_snapshot_id,
        match_id=prediction.match_id,
        model_version=prediction.model_version,
        architecture_hash=prediction.architecture_hash,
        novig_method="proportional_two_way_v1",
        raw_implied_p_a=raw_a,
        raw_implied_p_b=raw_b,
        book_margin=margin,
        novig_p_a=novig_a,
        novig_p_b=novig_b,
        model_p_a=prediction.p_player_a,
        model_p_b=prediction.p_player_b,
        edge_a_pp=edge_a,
        edge_b_pp=edge_b,
        ev_a_per_unit=ev_a,
        ev_b_per_unit=ev_b,
        market_observed_at=market.observed_at,
        decision_eligible=eligible,
        reason_codes=tuple(reasons),
    )
